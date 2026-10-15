import json
import logging
from typing import Optional
from py_mini_racer import MiniRacer
from .environment_stubs import BOTGUARD_ENVIRONMENT_STUBS
from ...domain.exceptions import VmExecutionError

logger = logging.getLogger(__name__)

class BotguardV8Runtime:
    """
    Manages an embedded Google V8 engine instance via py_mini_racer.
    Runs the Botguard polymorphic VM in a sandboxed, browser-like environment.
    """

    def __init__(self, script_code: str, bytecode: str):
        self._script_code = script_code
        self._bytecode = bytecode
        self._mr: Optional[MiniRacer] = None
        self._initialize_runtime()

    def _initialize_runtime(self) -> None:
        try:
            self._mr = MiniRacer()
            # 1. Inject environment stubs
            self._mr.eval(BOTGUARD_ENVIRONMENT_STUBS)
            # 2. Evaluate botguard script
            self._mr.eval(self._script_code)
            # 3. Store bytecode
            self._mr.eval("window.__raw_bytecode = " + json.dumps(self._bytecode) + ";")
            # 4. Initialize botguard VM instance with callback and drain asynchronous timers
            init_code = """
            (function() {
                window.__bg_ready = false;
                window.__bg_instance = window.botguard.bg(window.__raw_bytecode, function() {
                    window.__bg_ready = true;
                });
                var passes = 30;
                while (passes-- > 0 && __timer_callbacks.length > 0) {
                    var cbs = __timer_callbacks.splice(0, __timer_callbacks.length);
                    for (var i = 0; i < cbs.length; i++) {
                        try { cbs[i](); } catch(e) {}
                    }
                }
            })()
            """
            self._mr.eval(init_code)
            logger.debug("Botguard V8 runtime initialized successfully")
        except Exception as e:
            raise VmExecutionError(f"Failed to initialize Botguard V8 runtime: {e}") from e

    def generate_token(self, query_hash: str, conversation_id: str = "") -> str:
        """
        Executes a snapshot in the V8 engine and generates a Content-Bound Botguard token.
        """
        if not self._mr:
            raise VmExecutionError("V8 runtime is not initialized")

        qh_json = json.dumps(query_hash)
        cid_json = json.dumps(conversation_id)

        eval_script = f"""
        (function() {{
            var bgObj = window.__bg_instance;
            if (!bgObj || typeof bgObj.invoke !== 'function') {{
                return "ERR:NoBgInstance";
            }}
            
            // Drain any pending timer or interval callbacks
            var passes = 20;
            while (passes-- > 0 && __timer_callbacks.length > 0) {{
                var cbs = __timer_callbacks.splice(0, __timer_callbacks.length);
                for (var i = 0; i < cbs.length; i++) {{
                    try {{ cbs[i](); }} catch(e) {{}}
                }}
            }}
            for (var j = 0; j < __interval_callbacks.length; j++) {{
                try {{ __interval_callbacks[j](); }} catch(e) {{}}
            }}
            
            var qhObj = [{{ qh: {qh_json}, cid: {cid_json} }}];
            var token = null;
            var res = bgObj.invoke(function(asyncToken) {{
                token = asyncToken;
            }}, false, qhObj);
            
            // Drain any timer callbacks scheduled during invoke execution
            var postPasses = 20;
            while (postPasses-- > 0 && __timer_callbacks.length > 0) {{
                var postCbs = __timer_callbacks.splice(0, __timer_callbacks.length);
                for (var k = 0; k < postCbs.length; k++) {{
                    try {{ postCbs[k](); }} catch(e) {{}}
                }}
            }}
            
            return token || res;
        }})()
        """

        try:
            token = self._mr.eval(eval_script)
            if not token or not isinstance(token, str):
                raise VmExecutionError(f"V8 VM returned non-string token: {token}")

            if token.startswith("FNL") or token.startswith("ERR"):
                raise VmExecutionError(f"Botguard VM execution failed with status: {token}")

            if not token.startswith("!"):
                raise VmExecutionError(f"Botguard VM output missing '!' prefix: {token[:30]}")

            return token
        except VmExecutionError:
            raise
        except Exception as e:
            raise VmExecutionError(f"Failed to generate Botguard token in V8: {e}") from e

    def close(self) -> None:
        """
        Explicitly disposes the MiniRacer V8 isolate instance to reclaim memory.
        """
        self._mr = None
