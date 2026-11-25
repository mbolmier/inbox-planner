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
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    events: "/api/calendrier",
  });
  calendar.render();

  // Sent by the server (HX-Trigger header) after an energy change.
  document.body.addEventListener("planChanged", () => calendar.refetchEvents());
});
