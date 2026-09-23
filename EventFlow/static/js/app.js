
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-modal]").forEach(btn => {
    btn.addEventListener("click", () => {
      const modal = document.getElementById(btn.dataset.modal);
      if (modal) modal.classList.add("open");
    });
  });
  document.querySelectorAll("[data-close]").forEach(btn => {
    btn.addEventListener("click", () => btn.closest(".modal")?.classList.remove("open"));
  });
  document.querySelectorAll(".modal").forEach(modal => {
    modal.addEventListener("click", e => { if (e.target === modal) modal.classList.remove("open"); });
  });
  document.querySelectorAll("form[data-confirm]").forEach(form => {
    form.addEventListener("submit", e => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
  setTimeout(() => document.querySelectorAll(".flash").forEach(x => x.remove()), 3500);
});


(function(){
  function fmt(sec){
    sec=Math.max(0,Math.floor(sec));
    var h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), s=sec%60;
    return h ? String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')
              : m+'m '+String(s).padStart(2,'0')+'s';
  }
  function tick(){
    document.querySelectorAll('.task-timer').forEach(function(el){
      var base=parseInt(el.dataset.elapsed||'0',10);
      var st=el.dataset.started;
      if(st){
        var started=Date.parse(st);
        if(!isNaN(started)) base += Math.max(0,Math.floor((Date.now()-started)/1000));
      }
      el.textContent=fmt(base);
    });
  }
  tick();
  setInterval(tick,1000);
})();
