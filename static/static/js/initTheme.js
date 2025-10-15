const body = document.body;
const theme = localStorage.getItem('theme')

if (theme) 
  document.documentElement.setAttribute('data-bs-theme', theme)


(function(){
  const ACTIVE_PARENT_SELECTOR = '.sidebar-item.has-sub';
  const CHILD_LINK_SELECTOR = '.submenu-link';

  function clearActive(){
    document.querySelectorAll(ACTIVE_PARENT_SELECTOR).forEach(li=>li.classList.remove('active'));
    document.querySelectorAll(CHILD_LINK_SELECTOR).forEach(a=>a.classList.remove('active'));
  }

  function markByPath(path){
    if(!path) path = location.pathname;
    let found = document.querySelector(`${CHILD_LINK_SELECTOR}[href="${path}"]`);
    if(!found){
      found = Array.from(document.querySelectorAll(CHILD_LINK_SELECTOR)).find(a => {
        try { return a.getAttribute('href') && path.startsWith(a.getAttribute('href')); } catch(e){ return false; }
      }) || null;
    }
    clearActive();
    if(found){
      found.classList.add('active');
      const parent = found.closest('.sidebar-item.has-sub');
      if(parent) parent.classList.add('active');
    }
  }

  document.body.addEventListener('click', function(e){
    const a = e.target.closest(CHILD_LINK_SELECTOR);
    if(!a) return;
    const href = a.getAttribute('href');
    if(!href || href === '#') return;
    clearActive();
    a.classList.add('active');
    const parent = a.closest('.sidebar-item.has-sub');
    if(parent) parent.classList.add('active');
    try { history.pushState({}, '', href); } catch(err){}
    try { localStorage.setItem('sidebar_active_path', href); } catch(e){}
  }, {capture: true});

  document.addEventListener('DOMContentLoaded', ()=> {
    const nav = document.querySelector('#sidebar nav, #sidebar');
    const serverActive = nav && nav.dataset && nav.dataset.active;
    const saved = localStorage.getItem('sidebar_active_path');
    if(serverActive){
      markByPath(serverActive);
    } else if(saved && saved !== 'null'){
      markByPath(saved);
    } else {
      markByPath(location.pathname);
    }
  });

  document.body.addEventListener('htmx:afterSwap', ()=> setTimeout(()=> markByPath(location.pathname), 10));
  window.addEventListener('popstate', ()=> markByPath(location.pathname));
})();
