const UI = {
    form: document.getElementById('urlForm'),
    input: document.getElementById('urlInput'),
    btn: document.getElementById('shortenBtn'),
    error: document.getElementById('errorMsg'),
    result: document.getElementById('resultBox'),
    link: document.getElementById('shortLink'),
    copy: document.getElementById('copyBtn'),
    themeToggle: document.getElementById('themeToggle'),
    recentBox: document.getElementById('recentBox'),
    recentList: document.getElementById('recentList')
};

const toggleTheme = () => {
    const isDark = document.body.getAttribute('data-theme') !== 'light';
    document.body.setAttribute('data-theme', isDark ? 'light' : 'dark');
    UI.themeToggle.innerHTML = isDark ? '🌙' : '☀️';
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
};

const getRecent = () => JSON.parse(localStorage.getItem('recent_links') || '[]');
const saveRecent = (orig, short) => {
    const list = [{orig, short}, ...getRecent().filter(i => i.orig !== orig)].slice(0, 3);
    localStorage.setItem('recent_links', JSON.stringify(list));
    renderRecent();
};

const renderRecent = () => {
    const list = getRecent();
    if (!list.length) return UI.recentBox.classList.add('hidden');
    UI.recentBox.classList.remove('hidden');
    UI.recentList.innerHTML = list.map(i => `
        <div class="link-item">
            <div class="link-info">
                <a href="${i.short}" target="_blank">${i.short}</a>
                <span>${i.orig}</span>
            </div>
            <button class="copy-btn" onclick="copyText('${i.short}', this)">Copy</button>
        </div>
    `).join('');
};

const copyText = (text, btn) => {
    const success = () => {
        const old = btn.innerText; btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = old, 2000);
    };
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(success);
    } else {
        const t = document.createElement('textarea'); t.value = text;
        Object.assign(t.style, {position: 'fixed', opacity: '0'});
        document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove();
        success();
    }
};

if (localStorage.getItem('theme') === 'light') toggleTheme();
UI.themeToggle.addEventListener('click', toggleTheme);
UI.copy.addEventListener('click', () => copyText(UI.link.innerText, UI.copy));

UI.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = UI.input.value.trim();
    try { new URL(url); UI.error.classList.add('hidden'); } 
    catch { 
        UI.error.textContent = "Please enter a valid URL (http:// or https://)";
        UI.error.classList.remove('hidden'); UI.result.classList.add('hidden'); return;
    }

    UI.btn.innerText = 'Wait...'; UI.btn.disabled = true;
    try {
        const res = await fetch('/shorten', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (!res.ok) {
            if (res.status === 429) throw new Error('Thao tác quá nhanh! Vui lòng thử lại sau.');
            throw new Error('Server error. Could not shorten.');
        }
        const { short_url } = await res.json();
        
        UI.link.href = UI.link.innerText = short_url;
        UI.result.classList.remove('hidden');
        saveRecent(url, short_url);
    } catch (err) {
        UI.error.textContent = err.message || "Server error. Could not shorten.";
        UI.error.classList.remove('hidden'); UI.result.classList.add('hidden');
    } finally {
        UI.btn.innerText = 'Shorten'; UI.btn.disabled = false;
    }
});

renderRecent();
