(function() {

  function initCommunityUI() {
    // Para la foto
    const input = document.getElementById('visual_identity_input');
    const previewContainer = document.getElementById('visual_identity_preview_container');
    const previewImg = document.getElementById('visual_identity_preview');

    if (input) {
      const updatePreview = () => {
        const val = input.value.trim();
        if (!val) {
          previewContainer && (previewContainer.style.display = 'none');
          previewImg && (previewImg.src = '');
        } else {
          previewImg && (previewImg.src = val);
          previewContainer && (previewContainer.style.display = 'block');
        }
      };

      input.addEventListener('input', updatePreview);
      document.addEventListener('DOMContentLoaded', updatePreview);
    }
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', initCommunityUI)
    : initCommunityUI();

})();
