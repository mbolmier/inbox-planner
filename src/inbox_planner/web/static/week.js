// Week calendar (FullCalendar). The server sends local Oregon wall-clock times
// without an offset, so the browser shows them as they are, whatever its zone.
//
// Two views: "Par jour" (default) where every box grows with its text, so it is
// always shown in full, and "Grille horaire" where box heights follow durations.
// A work session shows one short line per task; a click opens the full detail.
//
// Everything is built with textContent, never as HTML: on a real mailbox the
// titles come from e-mails written by strangers. Links are the app's own pages
// or https links checked on the server.
document.addEventListener("DOMContentLoaded", () => {
  const element = document.getElementById("calendar");
  if (!element || !window.FullCalendar) return;

  const VIEW_KEY = "inbox-planner-week-view";
  const views = ["dayGridWeek", "timeGridWeek"];
  const savedView = localStorage.getItem(VIEW_KEY);

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const link = (href, text, external) => {
    const a = el("a", null, text);
    a.href = href;
    if (external) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    return a;
  };

  const calendar = new FullCalendar.Calendar(element, {
    initialView: views.includes(savedView) ? savedView : "dayGridWeek",
    initialDate: element.dataset.initialDate,
    now: element.dataset.now, // the frozen demo clock
    locale: "fr",
    firstDay: 1,
    headerToolbar: { left: "title", center: "", right: "dayGridWeek,timeGridWeek" },
    buttonText: { dayGridWeek: "Par jour", timeGridWeek: "Grille horaire" },
    height: "auto",
    events: element.dataset.events,
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    displayEventEnd: true,
    defaultTimedEventDuration: "00:15", // deadlines have no end: a short mark in the grid
    // A 23:59 deadline then ends at 00:14 the next day: keep it on its own day.
    nextDayThreshold: "06:00:00",
    eventOrder: "start,title",
    views: {
      dayGridWeek: { eventDisplay: "block", dayMaxEvents: false },
      timeGridWeek: {
        allDaySlot: false,
        slotMinTime: "07:00:00",
        slotMaxTime: "24:00:00", // 23:59 deadlines stay visible
        nowIndicator: true,
        slotEventOverlap: false, // simultaneous items side by side, never stacked
        eventMinHeight: 26,
        expandRows: true,
      },
    },
    eventContent: (arg) => {
      const box = el("div", "ev");
      box.append(el("span", "ev-time", arg.timeText), " ");
      const info = arg.event.extendedProps;
      if (info.kind === "session") {
        box.append(el("span", "ev-title", arg.event.title));
        const list = el("ul", "ev-parts");
        for (const part of info.parts) list.append(el("li", null, part.short));
        box.append(list);
      } else {
        box.append(el("span", "ev-title", arg.event.title));
      }
      return { domNodes: [box] };
    },
    eventDidMount: (info) => {
      info.el.title = `${info.timeText} · ${info.event.title} (cliquer pour le détail)`;
    },
    eventClick: (info) => {
      info.jsEvent.preventDefault();
      showDetail(info.event);
    },
    viewDidMount: (info) => localStorage.setItem(VIEW_KEY, info.view.type),
  });
  calendar.render();

  const dialog = document.getElementById("detail");
  const body = document.getElementById("detail-body");

  function showDetail(event) {
    const info = event.extendedProps;
    body.replaceChildren();
    const head = el("h2", null, info.kind === "deadline" ? "Échéance" : info.title);
    head.id = "detail-title";
    body.append(head, el("p", "muted mono", `${info.day} · ${info.time}`));
    if (info.kind === "event") {
      if (info.place) {
        const where = el("p", "detail-place");
        where.append(
          info.place.online
            ? link(info.place.url, `Rejoindre sur ${info.place.label}`, true)
            : link(info.place.url, `📍 ${info.place.label}`, true),
        );
        body.append(where);
      }
    }
    const list = el("ul", "detail-parts");
    for (const part of info.parts) {
      const item = el("li", "detail-part");
      const title = el("p", "detail-task");
      title.append(el("span", "tag", part.tag), " ", part.title);
      const meta = el("p", "meta");
      if (part.time) meta.append(el("span", "mono", part.time));
      meta.append(el("span", "mono", `≈ ${part.minutes}`));
      meta.append(el("span", null, `échéance ${part.due}`));
      meta.append(el("span", `jn u-${part.urgency}`, part.countdown));
      const links = el("p", "detail-links");
      if (part.mail) links.append(link(part.mail, "Voir le mail ↗"));
      if (part.site) links.append(link(part.site, "Ouvrir le site ↗", true));
      item.append(title, meta, links);
      list.append(item);
    }
    if (info.parts.length) body.append(list);
    if (info.kind === "event" && info.mail) {
      const links = el("p", "detail-links");
      links.append(link(info.mail, "Voir le mail ↗"));
      body.append(links);
    }
    dialog.showModal();
  }

  // Close when clicking outside the box.
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  // Sent by the server (HX-Trigger header) after an energy change.
  document.body.addEventListener("planChanged", () => calendar.refetchEvents());
});
