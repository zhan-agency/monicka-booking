(() => {
  const form = document.getElementById("assessment-form");
  if (!form) return;
  const pages = [...form.querySelectorAll(".assessment-question")];
  const previous = document.getElementById("assessment-prev");
  const next = document.getElementById("assessment-next");
  const submit = document.getElementById("assessment-submit");
  const progress = document.getElementById("assessment-progress");
  const label = document.getElementById("assessment-progress-label");
  const live = document.getElementById("assessment-live");
  let current = 0;
  function show(index, announce = true) {
    current = index;
    pages.forEach((page, i) => { page.hidden = i !== current; });
    previous.disabled = current === 0;
    next.hidden = current === pages.length - 1;
    submit.hidden = current !== pages.length - 1;
    progress.value = current + 1;
    label.textContent = `پرسش ${current + 1} از ${pages.length}`;
    if (announce) {
      live.textContent = label.textContent;
      pages[current].querySelector("legend").setAttribute("tabindex", "-1");
      pages[current].querySelector("legend").focus({preventScroll: true});
      pages[current].scrollIntoView({behavior: "smooth", block: "start"});
    }
  }
  next.addEventListener("click", () => {
    const answer = pages[current].querySelector("input[type=radio]:checked");
    if (!answer) {
      const first = pages[current].querySelector("input[type=radio]");
      first.focus();
      live.textContent = "لطفاً به این پرسش پاسخ دهید.";
      return;
    }
    show(Math.min(current + 1, pages.length - 1));
  });
  previous.addEventListener("click", () => show(Math.max(current - 1, 0)));
  form.addEventListener("submit", event => {
    const unanswered = pages.findIndex(page => !page.querySelector("input[type=radio]:checked"));
    if (unanswered !== -1) {
      event.preventDefault();
      show(unanswered);
      live.textContent = "هنوز به همه پرسش‌ها پاسخ نداده‌اید.";
      pages[unanswered].querySelector("input[type=radio]").focus();
    }
  });
  show(0, false);
})();
