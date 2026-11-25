// Week calendar (FullCalendar). The server sends local Oregon wall-clock times
// without an offset, so the browser shows them as they are, whatever its zone.
//
// Two views: "Par jour" (default) where every box grows with its text, so it is
// always shown in full, and "Grille horaire" where box heights follow durations.
document.addEventListener("DOMContentLoaded", () => {
  const element = document.getElementById("calendar");
  if (!element || !window.FullCalendar) return;

  const VIEW_KEY = "inbox-planner-week-view";
  const views = ["dayGridWeek", "timeGridWeek"];
  const savedView = localStorage.getItem(VIEW_KEY);

  const calendar = new FullCalendar.Calendar(element, {
    initialView: views.includes(savedView) ? savedView : "dayGridWeek",
    initialDate: element.dataset.initialDate,
    now: element.dataset.now, // the frozen demo clock
    locale: "fr",
    firstDay: 1,
    headerToolbar: { left: "title", center: "", right: "dayGridWeek,timeGridWeek" },
    buttonText: { dayGridWeek: "Par jour", timeGridWeek: "Grille horaire" },
    height: "auto",
    events: "/api/calendrier",
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
    // Time then title, built with textContent and never as HTML: on a real
    // mailbox the titles come from e-mails written by strangers.
    eventContent: (arg) => {
      const box = document.createElement("div");
      box.className = "ev";
      const time = document.createElement("span");
      time.className = "ev-time";
      time.textContent = arg.timeText;
      const title = document.createElement("span");
      title.className = "ev-title";
      title.textContent = arg.event.title;
      box.append(time, " ", title);
      return { domNodes: [box] };
    },
    eventDidMount: (info) => {
      info.el.title = `${info.timeText} · ${info.event.title}`; // full title on hover
    },
    viewDidMount: (info) => localStorage.setItem(VIEW_KEY, info.view.type),
  });
  calendar.render();

  // Sent by the server (HX-Trigger header) after an energy change.
  document.body.addEventListener("planChanged", () => calendar.refetchEvents());
});
