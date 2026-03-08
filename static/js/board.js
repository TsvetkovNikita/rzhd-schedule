
(() => {
  const root = document.documentElement;
  const tz = root.dataset.tz;
  let ms = Number(root.dataset.nowEpochMs || 0);

  const dateEl = document.querySelector('.clock .date');
  const timeEl = document.querySelector('.clock .time');

  const fmtDate = new Intl.DateTimeFormat('en-CA', {
    timeZone: tz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });

  const fmtTime = new Intl.DateTimeFormat('ru-RU', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });

  function renderClock() {
    if (!dateEl || !timeEl) return;
    const d = new Date(ms);
    dateEl.textContent = fmtDate.format(d);
    timeEl.textContent = fmtTime.format(d);
  }

  function setupRouteScrolling() {
    const routeContainers = document.querySelectorAll('.route-container');
    routeContainers.forEach(container => {
      const textElement = container.querySelector('.route-text');
      if (!textElement) return;
      const containerWidth = container.clientWidth;
      const textWidth = textElement.scrollWidth;
      if (textWidth > containerWidth) {
        textElement.classList.add('scrolling');
        const extraWidth = textWidth - containerWidth;
        const duration = 10 + (extraWidth / 50);
        textElement.style.setProperty('--scroll-duration', `${duration}s`);
        textElement.style.setProperty('--scroll-offset', `-${extraWidth}px`);
      } else {
        textElement.classList.remove('scrolling');
        textElement.style.removeProperty('--scroll-offset');
      }
    });
  }

  renderClock();
  setInterval(() => {
    ms += 1000;
    renderClock();
  }, 1000);

  window.addEventListener('load', setupRouteScrolling);
  window.addEventListener('resize', setupRouteScrolling);
  setTimeout(setupRouteScrolling, 100);
})();
