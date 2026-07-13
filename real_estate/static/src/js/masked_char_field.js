/** @odoo-module **/

import { registry } from "@web/core/registry";
import { charField, CharField } from "@web/views/fields/char/char_field";
import { onMounted } from "@odoo/owl";

/**
 * `widget="mask"` is used throughout this codebase (CNIC, mobile numbers, ...) via
 * `data-inputmask="'mask': '99999-9999999-9'"`, a convention carried over from an
 * old OCA-style jQuery inputmask widget. Odoo dropped jQuery widgets years ago and
 * no replacement was ever registered for Odoo 19's OWL field registry, so every
 * `widget="mask"` field silently fell back to a plain CharField: no auto-inserted
 * separators, no max-length enforcement. This registers an actual "mask" field so
 * that existing/future `widget="mask"` declarations work.
 *
 * Mask syntax (matches the existing `data-inputmask` strings already in the XML):
 * '9' is a digit placeholder, any other character is a literal that gets
 * auto-inserted and is never itself typed by the user.
 */

function digitsOf(pattern) {
    return pattern.split("").filter((c) => c === "9").length;
}

function applyMask(pattern, digits) {
    let out = "";
    let di = 0;
    for (const ch of pattern) {
        if (di >= digits.length) {
            break;
        }
        if (ch === "9") {
            out += digits[di];
            di++;
        } else {
            out += ch;
        }
    }
    return out;
}

function parseMaskAttr(raw) {
    if (!raw) {
        return "";
    }
    const match = raw.match(/mask['"]?\s*:\s*['"]([^'"]*)['"]/);
    return match ? match[1] : "";
}

export class MaskedCharField extends CharField {
    setup() {
        super.setup();
        const pattern = this.props.inputMask;
        if (!pattern) {
            return;
        }
        onMounted(() => {
            const el = this.input.el;
            if (!el) {
                return;
            }
            const reformat = () => {
                const digits = el.value.replace(/\D/g, "").slice(0, digitsOf(pattern));
                const formatted = applyMask(pattern, digits);
                if (el.value !== formatted) {
                    el.value = formatted;
                }
            };
            // Capture phase so this runs — and rewrites el.value — before CharField's
            // own bubble-phase input listener (from useInputField) reads it.
            el.addEventListener("input", reformat, true);
            reformat();
        });
    }

    // Most of these fields (cnic, kin_cnic, ...) are readonly="id" — editable only
    // while the record is new, readonly (a plain <span>, no <input>) once saved. The
    // "input" listener above never runs for that <span>, so old values already
    // stored without dashes would otherwise display unformatted forever. Reformat
    // here too so the readonly view always shows the masked value.
    get formattedValue() {
        const pattern = this.props.inputMask;
        const value = super.formattedValue;
        if (!pattern || !value) {
            return value;
        }
        const digits = value.replace(/\D/g, "").slice(0, digitsOf(pattern));
        return applyMask(pattern, digits);
    }
}
MaskedCharField.props = {
    ...CharField.props,
    inputMask: { type: String, optional: true },
};

export const maskedCharField = {
    ...charField,
    component: MaskedCharField,
    extractProps(fieldInfo) {
        const props = charField.extractProps(fieldInfo);
        props.inputMask = parseMaskAttr(fieldInfo.attrs["data-inputmask"]);
        return props;
    },
};

registry.category("fields").add("mask", maskedCharField);
