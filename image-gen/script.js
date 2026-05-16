const API = '/api';
let currentStyle = 'academic';
let currentSize = '1536x1024';
let startTime = 0;
let history = [];
let uploadedImage = null; // base64 data (no prefix)
const _$ = function(id){ return document.getElementById(id); };

/* === Access Gate === */
function checkGate() {
  var ans = _$('gateInput').value.trim();
  if (ans === '\u758F\u9526\u884C') {
    localStorage.setItem('ai_studio_unlocked', '1');
    _$('gateOverlay').classList.add('hidden');
    toast('Welcome!', 'success');
  } else {
    _$('gateError').textContent = '\u2716 \u7B54\u6848\u4E0D\u6B63\u786E\uFF0C\u8BF7\u91CD\u8BD5';
    _$('gateInput').value = '';
    _$('gateInput').focus();
  }
}

function initGate() {
  if (localStorage.getItem('ai_studio_unlocked') === '1') {
    _$('gateOverlay').classList.add('hidden');
  } else {
    _$('gateInput').addEventListener('keydown', function(e){
      if (e.key === 'Enter') checkGate();
    });
    _$('gateInput').focus();
  }
}

/* === Utils === */
function escapeHtml(s) {
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function toast(msg, type) {
  type = type || 'info';
  var el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function(){ el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(function(){ el.remove(); }, 300); }, 2500);
}

function updateCC() {
  var len = _$('prompt').value.length;
  _$('charCount').textContent = len + '/1000';
}

function selectStyle(el) {
  document.querySelectorAll('.style-item').forEach(function(b){ b.classList.remove('active'); });
  el.classList.add('active');
  currentStyle = el.dataset.style;
}

function selectSize(el) {
  document.querySelectorAll('.size-pill').forEach(function(b){ b.classList.remove('active'); });
  el.classList.add('active');
  currentSize = el.dataset.size;
}

function copyText(id) {
  var el = _$(id);
  var t = el.value !== undefined ? el.value : el.textContent;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(function(){ toast('Copied!', 'success'); }).catch(function(){ fallbackCopy(t); });
  } else {
    fallbackCopy(t);
  }
}

function fallbackCopy(text) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;opacity:0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); toast('Copied!', 'success'); } catch(e) { toast('\u590D\u5236\u5931\u8D25', 'error'); }
  document.body.removeChild(ta);
}

function useOptimized() {
  var t = _$('optTA').value.trim();
  if (t) { _$('prompt').value = t; updateCC(); generate(); }
}

/* === Image Upload === */
function handleImageUpload(file) {
  if (!file || !file.type.startsWith('image/')) {
    toast('\u8BF7\u4E0A\u4F20\u56FE\u7247\u6587\u4EF6', 'error');
    return;
  }
  if (file.size > 4 * 1024 * 1024) {
    toast('\u56FE\u7247\u4E0D\u80FD\u8D85\u8FC7 4MB', 'error');
    return;
  }
  var reader = new FileReader();
  reader.onload = function(e) {
    var dataUrl = e.target.result;
    uploadedImage = dataUrl.split(',')[1];
    _$('previewUploadImg').src = dataUrl;
    _$('uploadFileName').textContent = file.name;
    _$('uploadPlaceholder').style.display = 'none';
    _$('uploadPreview').style.display = 'flex';
    _$('genBtn').innerHTML = '\u2728 \u56FE\u5230\u56FE\u4F18\u5316\u751F\u6210';
  };
  reader.readAsDataURL(file);
}

function removeUpload() {
  uploadedImage = null;
  _$('imageInput').value = '';
  _$('uploadPlaceholder').style.display = 'flex';
  _$('uploadPreview').style.display = 'none';
  _$('genBtn').innerHTML = '\u2728 \u5E76\u884C\u751F\u6210\u4E24\u5F20\u56FE\u7247';
}

function applyOpt() {
  var t = _$('optTA').value.trim();
  if (t) { _$('prompt').value = t; updateCC(); toast('Applied', 'success'); }
}

function openLB(src) { _$('lbImg').src = src; _$('lightbox').classList.add('show'); }
function closeLB() { _$('lightbox').classList.remove('show'); }

function addHist(imgId, sz, pr) {
  history.unshift({ id: imgId, size: sz, prompt: pr });
  if (history.length > 30) history.pop();
  renderHist();
}

function renderHist() {
  var box = _$('historyBox');
  if (!history.length) { box.style.display = 'none'; return; }
  box.style.display = 'block';
  _$('historyGrid').innerHTML = history.map(function(h){
    var safeId = escapeHtml(h.id);
    return '<div class="history-item" onclick="openLB(\'/api/image/' + safeId + '\')"><img src="/api/image/' + safeId + '" loading="lazy" onerror="this.parentElement.style.display=\'none\'"></div>';
  }).join('');
}

/* === Optimize === */
async function optimizePrompt() {
  var prompt = _$('prompt').value.trim();
  if (!prompt) { toast('\u8BF7\u5148\u8F93\u5165\u63CF\u8FF0', 'error'); return; }
  var btn = _$('optBtn');
  btn.disabled = true;
  btn.textContent = 'Optimizing...';
  try {
    var resp = await fetch(API + '/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, style: currentStyle })
    });
    var data = await resp.json();
    if (data.error) throw new Error(data.error);
    _$('optTA').value = data.optimized_prompt;
    _$('optMT').textContent = data.model || 'AI';
    _$('optResult').style.display = 'block';
    toast('\u63D0\u793A\u8BCD\u5DF2\u4F18\u5316', 'success');
  } catch (e) {
    toast('\u5931\u8D25: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '\u2728 \u667A\u80FD\u589E\u5F3A';
  }
}

/* === Generate (Dual) === */
async function generate() {
  var prompt = _$('prompt').value.trim();
  if (!prompt) { toast('\u8BF7\u8F93\u5165\u63CF\u8FF0', 'error'); return; }
  var btn = _$('genBtn');
  var dualGrid = _$('dualGrid');
  var pbar = _$('progressBar');
  var pfill = _$('progressFill');
  var status = _$('previewStatus');
  var ph = _$('placeholder');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> \u53CC\u53F7\u6C60\u5E76\u884C\u751F\u6210\u4E2D...';
  _$('optBtn').disabled = true;
  ph.style.display = 'none';
  dualGrid.style.display = 'none';
  dualGrid.innerHTML = '';
  _$('actions').style.display = 'none';
  _$('resultMeta').style.display = 'none';
  status.style.display = 'block';
  status.className = 'preview-status';
  status.textContent = 'AI \u6B63\u5728\u6784\u601D\u753B\u9762...';
  pbar.style.display = 'block';
  pfill.style.width = '0%';
  startTime = Date.now();

  var progress = 0;
  var tips = ['AI \u6B63\u5728\u6784\u601D\u753B\u9762...', '\u4E24\u4E2A\u53F7\u6C60\u5E76\u884C\u6E32\u67D3\u4E2D...', '\u7CBE\u4FEE\u7EC6\u8282\u4E2D...', '\u751F\u6210\u9AD8\u6E05\u56FE\u7247\u4E2D...'];
  var pTimer = setInterval(function(){
    var elapsed = (Date.now() - startTime) / 1000;
    if (elapsed < 20) progress = Math.min(progress + Math.random() * 5, 30);
    else if (elapsed < 50) progress = Math.min(progress + Math.random() * 3, 65);
    else progress = Math.min(progress + Math.random() * 2, 92);
    pfill.style.width = progress + '%';
    status.textContent = tips[Math.min(Math.floor(elapsed / 20), tips.length - 1)];
  }, 800);

  try {
    var resp = await fetch(API + '/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, size: currentSize, image: uploadedImage || undefined })
    });
    var text = await resp.text();
    var data;
    try { data = JSON.parse(text); } catch(pe) {
      console.error('Raw response:', text.substring(0, 500));
      throw new Error('\u670D\u52A1\u5668\u8FD4\u56DE\u4E86\u65E0\u6548\u6570\u636E (len=' + text.length + ')\uFF0C\u8BF7\u91CD\u8BD5');
    }
    if (data.error) throw new Error(data.error);
    clearInterval(pTimer);
    pfill.style.width = '100%';
    var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

    var images = data.images || [];
    if (!images.length) throw new Error('No images returned');

    dualGrid.innerHTML = images.map(function(img, i){
      var label = escapeHtml(img.pool || ('Image ' + (i+1)));
      var safeId = escapeHtml(img.image_id);
      return '<div class="dual-card">' +
        '<img src="/api/image/' + safeId + '" onclick="openLB(this.src)" alt="' + label + '">' +
        '<div class="card-footer">' +
          '<span class="pool-tag">' + label + '</span>' +
          '<div class="card-actions">' +
            '<a href="/api/image/' + safeId + '" download="ai-' + safeId + '.png">\u2B07 \u4E0B\u8F7D</a>' +
          '</div>' +
        '</div>' +
      '</div>';
    }).join('');
    dualGrid.style.display = 'grid';

    _$('metaModel').textContent = '\uD83E\uDD16 GPT-Image-2';
    _$('metaSize').textContent = '\uD83D\uDCCF ' + currentSize;
    _$('metaTime').textContent = '\u23F1\uFE0F ' + elapsed + 's \u00B7 ' + images.length + '\u5F20';
    _$('resultMeta').style.display = 'flex';
    _$('actions').style.display = 'flex';
    status.style.display = 'none';

    images.forEach(function(img){ addHist(img.image_id, img.size || currentSize, prompt); });
    toast(images.length + ' \u5F20\u56FE\u7247\u751F\u6210\u6210\u529F\uFF01', 'success');
    setTimeout(function(){ pbar.style.display = 'none'; }, 800);
  } catch (e) {
    clearInterval(pTimer);
    pbar.style.display = 'none';
    status.className = 'preview-status error';
    status.textContent = '\u5931\u8D25: ' + e.message;
    ph.style.display = 'flex';
    toast('\u751F\u6210\u5931\u8D25', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = uploadedImage ? '\u2728 \u56FE\u5230\u56FE\u4F18\u5316\u751F\u6210' : '\u2728 \u5E76\u884C\u751F\u6210\u4E24\u5F20\u56FE\u7247';
    _$('optBtn').disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', function(){
  initGate();
  _$('prompt').addEventListener('input', updateCC);
  _$('prompt').addEventListener('keydown', function(e){
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); generate(); }
  });
  updateCC();

  // Image upload: drag & drop
  var uploadArea = _$('uploadArea');
  uploadArea.addEventListener('dragover', function(e) { e.preventDefault(); uploadArea.classList.add('dragover'); });
  uploadArea.addEventListener('dragleave', function() { uploadArea.classList.remove('dragover'); });
  uploadArea.addEventListener('drop', function(e) {
    e.preventDefault(); uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleImageUpload(e.dataTransfer.files[0]);
  });
  _$('imageInput').addEventListener('change', function(e) {
    if (e.target.files.length) handleImageUpload(e.target.files[0]);
  });
});