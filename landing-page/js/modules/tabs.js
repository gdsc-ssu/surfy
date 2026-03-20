export function initTabs() {
  const tabs = document.querySelectorAll('.seq-tab');
  const panels = document.querySelectorAll('.seq-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;

      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      document.getElementById('panel-' + target).classList.add('active');
    });
  });
}
