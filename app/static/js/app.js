// Client-side Application JS - 100% Offline & Pure Vanilla JS
document.addEventListener("DOMContentLoaded", () => {
  const eventsGrid = document.getElementById("events-grid");
  const btnRefreshEvents = document.getElementById("btn-refresh-events");
  
  // Purchase Modal Elements
  const purchaseModal = document.getElementById("purchase-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const purchaseForm = document.getElementById("purchase-form");
  const modalEventTitle = document.getElementById("modal-event-title");
  const formEventId = document.getElementById("form-event-id");
  const formSelectedTicketId = document.getElementById("form-selected-ticket-id");
  const formBuyerName = document.getElementById("form-buyer-name");
  const formBuyerContact = document.getElementById("form-buyer-contact");
  const formQuantity = document.getElementById("form-quantity");
  const seatSelectionContainer = document.getElementById("seat-selection-container");
  const quantitySelectionContainer = document.getElementById("quantity-selection-container");
  const seatsGrid = document.getElementById("seats-grid");
  const selectedSeatLabel = document.getElementById("selected-seat-label");
  const summaryUnitPrice = document.getElementById("summary-unit-price");
  const summaryTotalPrice = document.getElementById("summary-total-price");
  const btnSubmitPurchase = document.getElementById("btn-submit-purchase");

  // Success Modal Elements
  const successModal = document.getElementById("success-modal");
  const successCloseBtn = document.getElementById("success-close-btn");
  const successTicketContainer = document.getElementById("success-ticket-container");
  const btnViewTicketPage = document.getElementById("btn-view-ticket-page");
  const btnBuyAnother = document.getElementById("btn-buy-another");

  let currentEvent = null;
  let activeSeats = [];

  // Show Toast
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Fetch and Render Events
  async function loadEvents() {
    try {
      const res = await fetch("/api/events");
      if (!res.ok) throw new Error("Error loading events");
      const events = await res.json();
      renderEvents(events);
    } catch (err) {
      eventsGrid.innerHTML = `
        <div style="text-align: center; grid-column: 1 / -1; padding: 2rem; color: var(--danger);">
          No se pudieron cargar los eventos. Verifica la conexión con el servidor local.
        </div>
      `;
    }
  }

  function renderEvents(events) {
    if (!events || events.length === 0) {
      eventsGrid.innerHTML = `
        <div style="text-align: center; grid-column: 1 / -1; padding: 3rem; color: var(--text-muted);">
          No hay eventos activos en este momento.
        </div>
      `;
      return;
    }

    eventsGrid.innerHTML = events.map(ev => {
      const percentSold = ev.total_capacity > 0 ? Math.round((ev.sold_tickets / ev.total_capacity) * 100) : 0;
      let barClass = "";
      if (percentSold >= 90) barClass = "full";
      else if (percentSold >= 70) barClass = "warning";

      const isSoldOut = ev.available_tickets <= 0;

      return `
        <div class="event-card">
          <div class="event-card-body">
            <div class="event-badge-price">$${ev.price.toFixed(2)}</div>
            <h3 class="event-title">${escapeHtml(ev.title)}</h3>
            <p class="event-desc">${escapeHtml(ev.description || "Entrada general para acceso al recinto.")}</p>
            
            <div class="capacity-container">
              <div class="capacity-info">
                <span>Disponibles: <strong>${ev.available_tickets}</strong> de ${ev.total_capacity}</span>
                <span>${percentSold}% vendido</span>
              </div>
              <div class="progress-bar-bg">
                <div class="progress-bar-fill ${barClass}" style="width: ${percentSold}%"></div>
              </div>
            </div>

            <button class="btn btn-primary btn-block btn-open-purchase" data-event-id="${ev.id}" ${isSoldOut ? "disabled" : ""}>
              ${isSoldOut ? "Agotado" : "Adquirir Entrada"}
            </button>
          </div>
        </div>
      `;
    }).join("");

    // Attach event listeners
    document.querySelectorAll(".btn-open-purchase").forEach(btn => {
      btn.addEventListener("click", () => {
        const evId = parseInt(btn.getAttribute("data-event-id"), 10);
        const ev = events.find(e => e.id === evId);
        if (ev) openPurchaseModal(ev);
      });
    });
  }

  // Open Purchase Modal
  async function openPurchaseModal(event) {
    currentEvent = event;
    modalEventTitle.innerText = event.title;
    formEventId.value = event.id;
    formSelectedTicketId.value = "";
    formBuyerName.value = "";
    formBuyerContact.value = "";
    formQuantity.value = "1";
    selectedSeatLabel.innerText = "Ningún asiento seleccionado";

    summaryUnitPrice.innerText = `$${event.price.toFixed(2)}`;
    updateTotalSummary();

    // Check if event has seat map
    try {
      const res = await fetch(`/api/events/${event.id}/seats`);
      const seats = await res.json();
      activeSeats = seats;

      if (seats && seats.length > 0) {
        seatSelectionContainer.style.display = "block";
        quantitySelectionContainer.style.display = "none";
        renderSeatMap(seats);
      } else {
        seatSelectionContainer.style.display = "none";
        quantitySelectionContainer.style.display = "block";
      }
    } catch (e) {
      seatSelectionContainer.style.display = "none";
      quantitySelectionContainer.style.display = "block";
    }

    purchaseModal.classList.add("active");
  }

  function renderSeatMap(seats) {
    seatsGrid.innerHTML = seats.map(s => {
      const isAvail = s.status === "AVAILABLE";
      return `
        <button type="button" class="seat-btn ${!isAvail ? 'sold' : ''}" data-ticket-id="${s.id}" data-seat="${s.seat_number}" ${!isAvail ? 'disabled' : ''}>
          ${escapeHtml(s.seat_number)}
        </button>
      `;
    }).join("");

    document.querySelectorAll(".seat-btn:not([disabled])").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".seat-btn").forEach(b => b.classList.remove("selected"));
        btn.classList.add("selected");
        const tId = btn.getAttribute("data-ticket-id");
        const sNum = btn.getAttribute("data-seat");
        formSelectedTicketId.value = tId;
        selectedSeatLabel.innerText = `Asiento seleccionado: ${sNum}`;
        updateTotalSummary();
      });
    });
  }

  function updateTotalSummary() {
    if (!currentEvent) return;
    let qty = 1;
    if (seatSelectionContainer.style.display === "none") {
      qty = parseInt(formQuantity.value, 10) || 1;
    }
    const total = currentEvent.price * qty;
    summaryTotalPrice.innerText = `$${total.toFixed(2)}`;
  }

  formQuantity.addEventListener("change", updateTotalSummary);

  function closePurchaseModal() {
    purchaseModal.classList.remove("active");
  }

  modalCloseBtn.addEventListener("click", closePurchaseModal);
  purchaseModal.addEventListener("click", (e) => {
    if (e.target === purchaseModal) closePurchaseModal();
  });

  // Handle Purchase Submit
  purchaseForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const buyerName = formBuyerName.value.trim();
    const buyerContact = formBuyerContact.value.trim();
    const eventId = parseInt(formEventId.value, 10);
    const hasSeats = seatSelectionContainer.style.display !== "none";
    const ticketId = formSelectedTicketId.value;
    const quantity = hasSeats ? 1 : parseInt(formQuantity.value, 10);

    if (hasSeats && !ticketId) {
      showToast("Por favor selecciona un asiento disponible.", "warning");
      return;
    }

    btnSubmitPurchase.disabled = true;
    btnSubmitPurchase.innerText = "Procesando boleto...";

    try {
      const payload = {
        event_id: eventId,
        ticket_id: hasSeats ? ticketId : null,
        quantity: quantity,
        buyer_name: buyerName,
        buyer_contact: buyerContact,
        payment_method: "CASH"
      };

      const res = await fetch("/api/tickets/purchase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Error al procesar la compra");
      }

      closePurchaseModal();
      showSuccessModal(data);
      loadEvents(); // Refresh capacity
      showToast("¡Boleto emitido exitosamente!", "success");

    } catch (err) {
      showToast(err.message, "danger");
      // If seat was taken, reload seats
      if (hasSeats && currentEvent) {
        const res = await fetch(`/api/events/${currentEvent.id}/seats`);
        const seats = await res.json();
        renderSeatMap(seats);
      }
    } finally {
      btnSubmitPurchase.disabled = false;
      btnSubmitPurchase.innerText = "Confirmar Compra y Generar Boleto QR";
    }
  });

  // Success Modal
  function showSuccessModal(data) {
    if (!data.tickets || data.tickets.length === 0) return;
    const firstTicket = data.tickets[0];

    btnViewTicketPage.href = `/ticket/${firstTicket.id}`;

    successTicketContainer.innerHTML = `
      <div style="background: white; border: 2px solid #0f172a; border-radius: var(--radius-md); padding: 1rem; margin-bottom: 0.5rem;">
        <img src="${firstTicket.qr_base64}" alt="QR Ticket" style="width: 180px; height: 180px; margin: 0 auto; display: block;">
        <div style="margin-top: 0.5rem; font-weight: 700; font-size: 1rem;">${escapeHtml(firstTicket.event_title || '')}</div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">Titular: <strong>${escapeHtml(firstTicket.buyer_name || '')}</strong></div>
        <div style="font-size: 0.85rem; color: var(--primary); font-weight: 600;">
          ${firstTicket.seat_number ? `Asiento: ${escapeHtml(firstTicket.seat_number)}` : `${data.tickets.length} Entrada(s) General`}
        </div>
      </div>
    `;

    successModal.classList.add("active");
  }

  function closeSuccessModal() {
    successModal.classList.remove("active");
  }

  successCloseBtn.addEventListener("click", closeSuccessModal);
  btnBuyAnother.addEventListener("click", closeSuccessModal);
  successModal.addEventListener("click", (e) => {
    if (e.target === successModal) closeSuccessModal();
  });

  btnRefreshEvents.addEventListener("click", loadEvents);

  // Helper escape
  function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    })[m]);
  }

  // Initial load
  loadEvents();
});
