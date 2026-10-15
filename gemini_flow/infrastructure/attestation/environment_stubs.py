"""
Environment stubs for executing Google's Botguard VM in an embedded V8 context.
Provides high-fidelity mock objects for window, document, iframe, navigator, and crypto.
"""

BOTGUARD_ENVIRONMENT_STUBS = """
var window = globalThis;
var self = globalThis;
var top = globalThis;
var parent = globalThis;

function atob(b64) {
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    var str = String(b64).replace(/=+$/, '');
    if (str.length % 4 === 1) throw new Error('InvalidLength');
    for (var bc = 0, bs, buffer, idx = 0, output = '';
        buffer = str.charAt(idx++);
        ~buffer && (bs = bc % 4 ? bs * 64 + buffer : buffer,
            bc++ % 4) ? output += String.fromCharCode(255 & bs >> (-2 * bc & 6)) : 0
    ) {
        buffer = chars.indexOf(buffer);
    }
    return output;
}

function btoa(bin) {
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    var str = String(bin);
    for (var block, charCode, idx = 0, map = chars, output = '';
        str.charAt(idx | 0) || (map = '=', idx % 1);
        output += map.charAt(63 & block >> 8 - idx % 1 * 8)) {
        charCode = str.charCodeAt(idx += 3 / 4);
        if (charCode > 0xFF) throw new Error('InvalidCharacter');
        block = block << 8 | charCode;
    }
    return output;
}
window.atob = atob;
window.btoa = btoa;

var __timer_callbacks = [];
window.setTimeout = function(fn, ms) {
    if (typeof fn === 'function') __timer_callbacks.push(fn);
    return 1;
};
window.clearTimeout = function(id) {};

var __interval_callbacks = [];
window.setInterval = function(fn, ms) {
    if (typeof fn === 'function') __interval_callbacks.push(fn);
    return 1;
};
window.clearInterval = function(id) {};
var setTimeout = window.setTimeout;
var clearTimeout = window.clearTimeout;
var setInterval = window.setInterval;
var clearInterval = window.clearInterval;

window.location = {
    href: "https://gemini.google.com/app",
    hostname: "gemini.google.com",
    protocol: "https:",
    origin: "https://gemini.google.com"
};

var createdIframes = [];

window.document = {
    createElement: function(tag) {
        var strTag = (typeof tag === 'string') ? tag : String(tag || '');
        var upperTag = strTag.toUpperCase();
        var el = {
            tagName: upperTag,
            style: {},
            src: "",
            _onload: null,
            get onload() { return this._onload; },
            set onload(fn) {
                this._onload = fn;
                if (typeof fn === "function") {
                    setTimeout(fn, 0);
                }
            },
            setAttribute: function(k, v) { el[k] = v; },
            getAttribute: function(k) { return el[k] || null; },
            appendChild: function(c) {
                if (c && typeof c.onload === "function") setTimeout(c.onload, 0);
            },
            removeChild: function() {},
            addEventListener: function(event, handler) {
                el["on" + event] = handler;
                if (event === "load" && typeof handler === "function") {
                    setTimeout(handler, 0);
                }
            },
            removeEventListener: function() {},
            contentWindow: {
                location: {
                    href: "https://gemini.google.com/_/bscframe"
                },
                postMessage: function() {},
                eval: function(code) {
                    return window.eval(code);
                }
            }
        };
        if (upperTag === "IFRAME") {
            createdIframes.push(el);
            setTimeout(function() {
                if (typeof el.onload === "function") el.onload();
            }, 0);
        }
        return el;
    },
    documentElement: { appendChild: function(c) { if (c && typeof c.onload === "function") setTimeout(c.onload, 0); }, removeChild: function() {}, lastChild: {} },
    head: { appendChild: function(c) { if (c && typeof c.onload === "function") setTimeout(c.onload, 0); } },
    body: { appendChild: function(c) { if (c && typeof c.onload === "function") setTimeout(c.onload, 0); }, removeChild: function() {} },
    getElementsByTagName: function() { return []; },
    querySelector: function() { return null; },
    querySelectorAll: function() { return []; },
    cookie: ""
};

window.navigator = {
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    platform: "Win32",
    language: "zh-TW",
    languages: ["zh-TW", "zh", "en"],
    hardwareConcurrency: 16,
    deviceMemory: 16,
    maxTouchPoints: 0,
    webdriver: false
};

window.screen = {
    width: 1920,
    height: 1080,
    availWidth: 1920,
    availHeight: 1040,
    colorDepth: 24,
    pixelDepth: 24
};

window.performance = {
    now: function() { return Date.now(); },
    timing: { navigationStart: Date.now() - 5000 }
};

window.crypto = {
    getRandomValues: function(buffer) {
        for (var i = 0; i < buffer.length; i++) {
            buffer[i] = Math.floor(Math.random() * 256);
        }
        return buffer;
    }
};

window.history = { length: 2 };
"""
