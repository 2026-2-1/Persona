(() => {
  const originalAddEventListener = EventTarget.prototype.addEventListener;
  const hoverEvents = new Set(['mouseenter', 'mouseover', 'pointerenter']);
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (hoverEvents.has(type) && this && typeof this.setAttribute === 'function') {
      try { this.setAttribute('data-maybe-hoverable', 'true'); } catch (_) { /* non-element target */ }
    }
    return originalAddEventListener.call(this, type, listener, options);
  };

  const activity = window.__uxagentNetworkActivity = {
    activeRequests: 0,
    lastActivity: Date.now(),
    listeners: new EventTarget(),
    update(delta, kind) {
      this.activeRequests = Math.max(0, this.activeRequests + delta);
      this.lastActivity = Date.now();
      this.listeners.dispatchEvent(new CustomEvent(delta > 0 ? 'start' : 'end', {detail: {kind}}));
    },
    waitForIdle(idleMs = 180, timeoutMs = 1000) {
      return new Promise(resolve => {
        let finished = false;
        let idleTimer;
        const finish = value => {
          if (finished) return;
          finished = true;
          clearTimeout(idleTimer);
          clearTimeout(hardTimer);
          this.listeners.removeEventListener('start', onStart);
          this.listeners.removeEventListener('end', onEnd);
          resolve(value);
        };
        const check = () => {
          clearTimeout(idleTimer);
          if (this.activeRequests === 0) {
            const wait = Math.max(0, idleMs - (Date.now() - this.lastActivity));
            idleTimer = setTimeout(() => finish(this.activeRequests === 0), wait);
          }
        };
        const onStart = () => { clearTimeout(idleTimer); };
        const onEnd = () => check();
        this.listeners.addEventListener('start', onStart);
        this.listeners.addEventListener('end', onEnd);
        const hardTimer = setTimeout(() => finish(false), timeoutMs);
        check();
      });
    }
  };

  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    let completed = false;
    const finish = () => {
      if (completed) return;
      completed = true;
      activity.update(-1, 'xhr');
    };
    activity.update(1, 'xhr');
    this.addEventListener('loadend', finish, {once: true});
    this.addEventListener('error', finish, {once: true});
    this.addEventListener('abort', finish, {once: true});
    try { return originalSend.apply(this, args); }
    catch (error) { finish(); throw error; }
  };

  const originalFetch = window.fetch;
  if (typeof originalFetch === 'function') {
    window.fetch = function (...args) {
      activity.update(1, 'fetch');
      let result;
      try { result = originalFetch.apply(this, args); }
      catch (error) { activity.update(-1, 'fetch'); throw error; }
      return result.finally(() => activity.update(-1, 'fetch'));
    };
  }
})();
