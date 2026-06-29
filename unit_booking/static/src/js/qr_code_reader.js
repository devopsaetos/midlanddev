/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Many2OneField, buildM2OFieldDescription } from "@web/views/fields/many2one/many2one_field";
import { onMounted } from "@odoo/owl";
import { ensureJQuery } from "@web/core/ensure_jquery";

function registerScannerDetection($) {
    if ($.fn.scannerDetection) return;
    $.fn.scannerDetection = function (options) {
        if (typeof options === "string") {
            this.each(function () { this.scannerDetectionTest(options); });
            return this;
        }
        if (options === false) {
            this.each(function () { this.scannerDetectionOff(); });
            return this;
        }
        const defaults = {
            onComplete: false,
            onError: false,
            onReceive: false,
            onKeyDetect: false,
            timeBeforeScanTest: 100,
            avgTimeByChar: 30,
            minLength: 6,
            endChar: [9, 13],
            startChar: [],
            ignoreIfFocusOn: false,
            scanButtonKeyCode: false,
            scanButtonLongPressThreshold: 3,
            onScanButtonLongPressed: false,
            stopPropagation: false,
            preventDefault: false,
        };
        if (typeof options === "function") options = { onComplete: options };
        options = typeof options !== "object" ? $.extend({}, defaults) : $.extend({}, defaults, options);

        this.each(function () {
            const self = this;
            const $self = $(self);
            let firstCharTime = 0, lastCharTime = 0, stringWriting = "", callIsScanner = false, testTimer = false, scanButtonCounter = 0;

            const initScannerDetection = () => {
                firstCharTime = 0;
                stringWriting = "";
                scanButtonCounter = 0;
            };

            self.scannerDetectionOff = () => {
                $self.unbind("keydown.scannerDetection");
                $self.unbind("keypress.scannerDetection");
            };

            self.isFocusOnIgnoredElement = () => {
                if (!options.ignoreIfFocusOn) return false;
                if (typeof options.ignoreIfFocusOn === "string") return $(':focus').is(options.ignoreIfFocusOn);
                if (typeof options.ignoreIfFocusOn === "object" && options.ignoreIfFocusOn.length) {
                    const focused = $(':focus');
                    for (let i = 0; i < options.ignoreIfFocusOn.length; i++) {
                        if (focused.is(options.ignoreIfFocusOn[i])) return true;
                    }
                }
                return false;
            };

            self.scannerDetectionTest = (s) => {
                if (s) { firstCharTime = lastCharTime = 0; stringWriting = s; }
                if (!scanButtonCounter) scanButtonCounter = 1;
                if (stringWriting.length >= options.minLength && lastCharTime - firstCharTime < stringWriting.length * options.avgTimeByChar) {
                    if (options.onScanButtonLongPressed && scanButtonCounter > options.scanButtonLongPressThreshold)
                        options.onScanButtonLongPressed.call(self, stringWriting, scanButtonCounter);
                    else if (options.onComplete)
                        options.onComplete.call(self, stringWriting, scanButtonCounter);
                    $self.trigger("scannerDetectionComplete", { string: stringWriting });
                    initScannerDetection();
                    return true;
                } else {
                    if (options.onError) options.onError.call(self, stringWriting);
                    $self.trigger("scannerDetectionError", { string: stringWriting });
                    initScannerDetection();
                    return false;
                }
            };

            $self.data("scannerDetection", { options })
                .unbind(".scannerDetection")
                .bind("keydown.scannerDetection", function (e) {
                    if (options.scanButtonKeyCode !== false && e.which === options.scanButtonKeyCode) {
                        scanButtonCounter++;
                        e.preventDefault();
                        e.stopImmediatePropagation();
                    } else if ((firstCharTime && options.endChar.indexOf(e.which) !== -1) ||
                               (!firstCharTime && options.startChar.indexOf(e.which) !== -1)) {
                        const e2 = $.Event("keypress", e);
                        e2.type = "keypress.scannerDetection";
                        $self.triggerHandler(e2);
                        e.preventDefault();
                        e.stopImmediatePropagation();
                    }
                    if (options.onKeyDetect) options.onKeyDetect.call(self, e);
                    $self.trigger("scannerDetectionKeyDetect", { evt: e });
                })
                .bind("keypress.scannerDetection", function (e) {
                    if (self.isFocusOnIgnoredElement()) return;
                    if (options.stopPropagation) e.stopImmediatePropagation();
                    if (options.preventDefault) e.preventDefault();
                    if (firstCharTime && options.endChar.indexOf(e.which) !== -1) {
                        e.preventDefault();
                        e.stopImmediatePropagation();
                        callIsScanner = true;
                    } else if (!firstCharTime && options.startChar.indexOf(e.which) !== -1) {
                        e.preventDefault();
                        e.stopImmediatePropagation();
                        callIsScanner = false;
                    } else {
                        if (typeof e.which !== "undefined") stringWriting += String.fromCharCode(e.which);
                        callIsScanner = false;
                    }
                    if (!firstCharTime) firstCharTime = Date.now();
                    lastCharTime = Date.now();
                    if (testTimer) clearTimeout(testTimer);
                    if (callIsScanner) {
                        self.scannerDetectionTest();
                        testTimer = false;
                    } else {
                        testTimer = setTimeout(self.scannerDetectionTest, options.timeBeforeScanTest);
                    }
                    if (options.onReceive) options.onReceive.call(self, e);
                    $self.trigger("scannerDetectionReceive", { evt: e });
                });
        });
        return this;
    };
}

class Many2oneInt extends Many2OneField {
    setup() {
        super.setup();
        onMounted(async () => {
            await ensureJQuery();
            const $ = window.$;
            registerScannerDetection($);

            const input = this.el && this.el.querySelector("input");
            if (!input) return;

            $(input).addClass("only_nums").scannerDetection({
                timeBeforeScanTest: 100,
                endChar: [74],
                avgTimeByChar: 40,
                onKeyDetect(e) {
                    console.log("first print", e.which, e.key);
                    return false;
                },
                onComplete(barcode) {
                    const result = barcode.substring(barcode.lastIndexOf("/") + 1);
                    $(".only_nums").val(result);
                    const checkExist = setInterval(() => {
                        if ($(".ui-widget-content>li").length) {
                            if ($(".ui-widget-content>li")[0].innerText === $(".only_nums").val()) {
                                $(".ui-widget-content>li").trigger("click");
                                clearInterval(checkExist);
                            }
                        }
                    }, 100);
                },
            });

            input.addEventListener("keypress", (evt) => {
                const keyentered = String.fromCharCode(evt.keyCode || evt.which);
                if (/^[a-zA-Z.,;:|\\\/~!@#$%^&*_\-{}\[\]()`"'<>?\s]+$/.test(keyentered)) {
                    evt.preventDefault();
                }
            });
        });
    }
}

registry.category("fields").add("m2o_int", buildM2OFieldDescription(Many2oneInt));
