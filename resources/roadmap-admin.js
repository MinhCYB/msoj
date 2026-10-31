document.addEventListener('DOMContentLoaded', function () {
    const search = document.getElementById('rm-tree-search');
    const tree = document.querySelector('.rm-sidebar > .rm-tree-list');
    if (!search || !tree) return;
    const rows = Array.from(tree.querySelectorAll('li[data-node-title]'));
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').toLowerCase();
    tree.querySelectorAll('[aria-current="page"]').forEach(link => {
        for (let parent = link.parentElement; parent && parent !== tree; parent = parent.parentElement) {
            if (parent.tagName === 'DETAILS') parent.open = true;
        }
    });
    let savedOpen = null;
    search.addEventListener('input', function () {
        const term = normalize(search.value.trim());
        if (term && !savedOpen) savedOpen = new Set(Array.from(tree.querySelectorAll('details[open]')));
        let found = false;
        rows.slice().reverse().forEach(row => {
            const ownMatch = normalize(row.dataset.nodeTitle).includes(term);
            const childMatch = Array.from(row.querySelectorAll('li[data-node-title]')).some(child => !child.hidden);
            row.hidden = !!term && !ownMatch && !childMatch;
            if (!row.hidden) found = true;
            const details = row.firstElementChild;
            if (term && details && details.tagName === 'DETAILS' && !row.hidden) details.open = true;
        });
        if (!term && savedOpen) {
            tree.querySelectorAll('details').forEach(details => { details.open = savedOpen.has(details); });
            savedOpen = null;
        }
        document.getElementById('rm-tree-result').hidden = found;
    });
});
