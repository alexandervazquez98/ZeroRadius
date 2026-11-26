/**
 * Bridge between the axios interceptor and the SessionManager dialog (#135).
 *
 * The SessionManager registers a handler that opens the sign-in dialog and
 * resolves once the admin signs in again (rejects if they sign out). Every
 * request that fails with 401 meanwhile waits on the same promise.
 */
let handler = null;
let pending = null;

export function setReauthHandler(fn) {
    handler = fn;
    return () => {
        if (handler === fn) {
            handler = null;
            pending = null; // a new owner must open its own dialog
        }
    };
}

export function hasReauthHandler() {
    return handler !== null;
}

export function requestReauth() {
    if (!handler) return Promise.reject(new Error('reauth-unavailable'));
    if (!pending) {
        pending = Promise.resolve()
            .then(handler)
            .finally(() => {
                pending = null;
            });
    }
    return pending;
}
