// search.js
// Placeholder search interaction script
function initSearch() {
    const searchInput = document.querySelector('.search-input');
    if (!searchInput) return;
    searchInput.addEventListener('input', function () {
        // Add search filtering logic here
        console.log('Searching for:', this.value);
    });
}
