(() => {
  const body = document.body;
  const openButton = document.querySelector('[data-sidebar-toggle]');
  const closeButtons = document.querySelectorAll('[data-sidebar-close]');

  const closeSidebar = () => {
    body.classList.remove('sidebar-open');
    if (openButton) openButton.setAttribute('aria-expanded', 'false');
  };

  if (openButton) {
    openButton.addEventListener('click', () => {
      const isOpen = body.classList.toggle('sidebar-open');
      openButton.setAttribute('aria-expanded', String(isOpen));
    });
  }
  closeButtons.forEach((button) => button.addEventListener('click', closeSidebar));
  window.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSidebar(); });
})();
