document.addEventListener('DOMContentLoaded', () => {
    wireFilters();
    const urlParams = new URLSearchParams(window.location.search);
    const q = urlParams.get('query') || '';
    const queryInput = document.getElementById('query');
    if (queryInput) {
        queryInput.value = q;
        queryInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
});

function wireFilters() {
    console.log("wire filters…");
    const filtersRoot = document.getElementById('filters');
    const results = document.getElementById('results');
    const notFound = document.getElementById('results_not_found');

    const inputs = filtersRoot.querySelectorAll(
        '#query,#title,#author,#affiliation,#tags,#start_date,#end_date,#doi,#min_size,#max_size,#publication_type,[name="sorting"]'
    );

    inputs.forEach(el => {
        const eventName = (el.type === 'radio' || el.tagName === 'SELECT') ? 'change' : 'input';
        el.addEventListener(eventName, runSearch);
    });

    document.getElementById('clear-filters').addEventListener('click', clearFilters);

    function runSearch() {
        results.innerHTML = '';
        notFound.style.display = 'none';

        const csrf = document.getElementById('csrf_token')?.value || null;

        const criteria = {
            csrf_token: csrf,
            query:            document.getElementById('query')?.value || '',
            title:            document.getElementById('title')?.value || '',
            author:           document.getElementById('author')?.value || '',
            affiliation:      document.getElementById('affiliation')?.value || '',
            publication_type: document.getElementById('publication_type')?.value || 'any',
            tags:             document.getElementById('tags')?.value || '',
            start_date:       document.getElementById('start_date')?.value || '',
            end_date:         document.getElementById('end_date')?.value || '',
            sorting:          (document.querySelector('[name="sorting"]:checked')?.value || 'newest'),
        };

        fetch('/explore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify(criteria),
        })
        .then(response => response.json())
        .then(data => {
            const count = data.length;
            const label = count === 1 ? 'dataset' : 'datasets';
            const counter = document.getElementById('results_number');
            if (counter) counter.textContent = `${count} ${label} found`;

            results.innerHTML = '';
            if (count === 0) {
                notFound.style.display = 'block';
                return;
            }

            data.forEach(dataset => {
                            let card = document.createElement('div');
                            card.className = 'col-12';
                            card.innerHTML = `
                                <div class="card">
                                    <div class="card-body">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <h3><a href="${dataset.url}">${dataset.title}</a></h3>
                                            <div>
                                                <span class="badge bg-primary" style="cursor: pointer;" onclick="set_publication_type_as_query('${dataset.publication_type}')">${dataset.publication_type}</span>
                                            </div>
                                        </div>
                                        <p class="text-secondary">${formatDate(dataset.created_at)}</p>

                                        <div class="row mb-2">

                                            <div class="col-md-4 col-12">
                                                <span class=" text-secondary">
                                                    Description
                                                </span>
                                            </div>
                                            <div class="col-md-8 col-12">
                                                <p class="card-text">${dataset.description}</p>
                                            </div>

                                        </div>

                                        <div class="row mb-2">

                                            <div class="col-md-4 col-12">
                                                <span class=" text-secondary">
                                                    Authors
                                                </span>
                                            </div>
                                            <div class="col-md-8 col-12">
                                                ${dataset.authors.map(author => `
                                                    <p class="p-0 m-0">${author.name}${author.affiliation ? ` (${author.affiliation})` : ''}${author.orcid ? ` (${author.orcid})` : ''}</p>
                                                `).join('')}
                                            </div>

                                        </div>

                                        <div class="row mb-2">

                                            <div class="col-md-4 col-12">
                                                <span class=" text-secondary">
                                                    Tags
                                                </span>
                                            </div>
                                            <div class="col-md-8 col-12">
                                                ${dataset.tags.map(tag => `<span class="badge bg-primary me-1" style="cursor: pointer;" onclick="set_tag_as_query('${tag}')">${tag}</span>`).join('')}
                                            </div>

                                        </div>

                                        <div class="row">

                                            <div class="col-md-4 col-12">

                                            </div>
                                            <div class="col-md-8 col-12">
                                                <a href="${dataset.url}" class="btn btn-outline-primary btn-sm" id="search" style="border-radius: 5px;">
                                                    View dataset
                                                </a>
                                                <a href="/dataset/download/${dataset.id}" class="btn btn-outline-primary btn-sm" id="search" style="border-radius: 5px;">
                                                    Download (${dataset.total_size_in_human_format})
                                                </a>
                                            </div>


                                        </div>

                                    </div>
                                </div>
                            `;

                            document.getElementById('results').appendChild(card);
                        });
        });
    }
}

function formatDate(dateString) {
    const d = new Date(dateString);
    return d.toLocaleString('en-US', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: 'numeric',
        minute: 'numeric'
    });
}

function set_tag_as_query(tagName) {
    const q = document.getElementById('query');
    q.value = tagName.trim();
    q.dispatchEvent(new Event('input', { bubbles: true }));
}

function set_publication_type_as_query(pt) {
    const sel = document.getElementById('publication_type');
    for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].text === pt.trim()) {
            sel.value = sel.options[i].value;
            break;
        }
    }
    sel.dispatchEvent(new Event('change', { bubbles: true }));
}

function clearFilters() {
    const ids = ['query', 'title', 'author', 'affiliation', 'tags', 'start_date', 'end_date', 'doi', 'min_size', 'max_size'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const type = document.getElementById('publication_type');
    if (type) type.value = 'any';
    const radios = document.querySelectorAll('[name="sorting"]');
    radios.forEach(r => r.checked = (r.value === 'newest'));
    document.getElementById('query').dispatchEvent(new Event('input', { bubbles: true }));
}
