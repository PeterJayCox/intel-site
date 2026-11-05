/* Flashforge-lite — the bias deck, embedded in a wiki page.
   No dependencies. Data arrives as JSON in #fc-data. */
(function () {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function init(root) {
    var dataEl = document.getElementById("fc-data");
    if (!dataEl) return;
    var data;
    try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
    var cards = data.cards || [];
    if (!cards.length) return;

    var order = cards.map(function (_, i) { return i; });
    var pos = 0;
    var flipped = false;

    var countEl = root.querySelector("[data-fc-count]");
    var famEl = root.querySelector("[data-fc-fam]");
    var cardEl = root.querySelector("[data-fc-card]");
    var frontEl = root.querySelector("[data-fc-front]");
    var backEl = root.querySelector("[data-fc-back]");
    var backTitle = root.querySelector("[data-fc-backtitle]");
    var backTell = root.querySelector("[data-fc-tell]");
    var backMove = root.querySelector("[data-fc-move]");

    function current() { return cards[order[pos]]; }

    function render() {
      var c = current();
      flipped = false;
      cardEl.classList.remove("is-flipped");
      cardEl.setAttribute("aria-pressed", "false");
      frontEl.textContent = c.front;
      backTitle.textContent = c.title;
      backTell.textContent = c.signature;
      backMove.textContent = c.move;
      countEl.textContent = (pos + 1) + " / " + cards.length;
      famEl.textContent = c.family + " · " + c.owner;
      famEl.setAttribute("data-family", c.family);
    }

    function flip() {
      flipped = !flipped;
      cardEl.classList.toggle("is-flipped", flipped);
      cardEl.setAttribute("aria-pressed", flipped ? "true" : "false");
    }

    function step(d) {
      pos = (pos + d + order.length) % order.length;
      render();
    }

    function shuffle() {
      for (var i = order.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var t = order[i]; order[i] = order[j]; order[j] = t;
      }
      pos = 0;
      render();
    }

    cardEl.addEventListener("click", flip);
    cardEl.addEventListener("keydown", function (e) {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    });

    root.querySelector("[data-fc-next]").addEventListener("click", function () { step(1); });
    root.querySelector("[data-fc-prev]").addEventListener("click", function () { step(-1); });
    root.querySelector("[data-fc-flip]").addEventListener("click", flip);
    root.querySelector("[data-fc-shuffle]").addEventListener("click", shuffle);

    document.addEventListener("keydown", function (e) {
      if (!root.contains(document.activeElement)) return;
      if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    });

    render();
    root.classList.add("is-ready");
  }

  function boot() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-fc-deck]"), init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
