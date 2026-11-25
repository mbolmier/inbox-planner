// Week calendar (FullCalendar). The server sends local Oregon wall-clock times
// without an offset, so the browser shows them as they are, whatever its zone.
document.addEventListener("DOMContentLoaded", () => {
  const element = document.getElementById("calendar");
  if (!element || !window.FullCalendar) return;

  const calendar = new FullCalendar.Calendar(element, {
    initialView: "timeGridWeek",
    initialDate: element.dataset.initialDate,
    now: element.dataset.now, // the frozen demo clock
    locale: "fr",
    firstDay: 1,
    headerToolbar: false,
    allDaySlot: false,
    slotMinTime: "07:00:00",
    slotMaxTime: "23:00:00",
    height: "auto",
    nowIndicator: true,
    slotEventOverlap: false, // simultaneous items side by side, never stacked on each other
    eventMinHeight: 26,
    expandRows: true,
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    events: "/api/calendrier",
    // Time and title on the same line; built with textContent, never as HTML,
    // because on a real mailbox the titles come from e-mails written by strangers.
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
  });
  calendar.render();

  // Sent by the server (HX-Trigger header) after an energy change.
  document.body.addEventListener("planChanged", () => calendar.refetchEvents());
});
