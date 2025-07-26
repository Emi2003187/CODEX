// Manejo de cancelar y eliminar consulta via AJAX

document.addEventListener('DOMContentLoaded', () => {
  function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const confirmMsg = form.dataset.confirm;
    if (confirmMsg && !confirm(confirmMsg)) {
      return;
    }
    const formData = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData,
      credentials: 'same-origin'
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          alert(`⚠️ ${data.error}`);
        } else if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else {
          window.location.reload();
        }
      })
      .catch(err => console.error(err));
  }

  document.querySelectorAll('form.js-consulta-cancelar, form.js-consulta-eliminar')
    .forEach(form => {
      form.addEventListener('submit', handleSubmit);
    });
});
