/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { IndexedDB } from "@web/core/utils/indexed_db";

/**
 * Core Odoo's IndexedDB helper (@web/core/utils/indexed_db) opens a fresh
 * connection on every execute() call and closes it once done, but never
 * listens for `db.onversionchange` - the event the browser fires on an
 * open connection when *another* tab/service-worker bumps the same
 * database's version. Without that handler, a connection left open while
 * a tab is idle/backgrounded can end up in the browser's "closing" state
 * behind the scenes; the next `db.transaction(...)` call on it then throws
 * `InvalidStateError: ... database connection is closing` as an uncaught
 * promise rejection (visible as the "UncaughtPromiseError" toast, e.g. on
 * the Investor Deal form after the tab sat idle for a few minutes).
 *
 * execute() always opens a brand new connection per call (no handle is
 * reused across calls), so retrying once is enough to recover.
 */
patch(IndexedDB.prototype, {
    async execute(callback) {
        try {
            return await super.execute(callback);
        } catch (e) {
            if (e && e.name === "InvalidStateError") {
                return await super.execute(callback);
            }
            throw e;
        }
    },
});
