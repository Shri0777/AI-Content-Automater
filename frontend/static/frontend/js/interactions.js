(() => {
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.allowResubmit === 'true') return;
    const submitter = event.submitter;
    if (submitter && submitter.matches('button[type="submit"]')) {
      submitter.disabled = true;
      submitter.dataset.originalLabel = submitter.textContent;
      submitter.textContent = 'Working…';
    }
  });

  document.addEventListener('click', (event) => {
    const action = event.target.closest('[data-confirm]');
    if (action && !window.confirm(action.dataset.confirm || 'Are you sure you want to continue?')) {
      event.preventDefault();
    }
  });
})();
