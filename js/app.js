const API_BASE_URL = "https://pharmacy-web-demo.onrender.com";

function formatPrice(value) {
  return `$${Number(value).toFixed(2)}`;
}

function renderStars(rating) {
  const rounded = Math.round(rating);
  let stars = "";

  for (let i = 1; i <= 5; i += 1) {
    stars += i <= rounded ? "★" : "☆";
  }

  return stars;
}

function createProductCard(product) {
  const savings = Math.max(product.rrp - product.currentPrice, 0);

  return `
    <article class="product-card">
      <div class="product-top">
        ${product.onSale ? '<span class="sale-badge">On Sale</span>' : ""}
        <!-- PLACEHOLDER: product image can replace this block later -->
        ${
            product.image
                ? `<img src="${product.image}" alt="${product.name}" class="product-image" />`
                : `<div class="product-image-placeholder">Product Image Placeholder</div>`
        }
      </div>

      <div class="product-body">
        <h3 class="product-name">${product.name}</h3>

        <div class="product-meta">
          ${product.gender} · ${product.productId}
        </div>

        <div class="product-rating" aria-label="Rated ${product.averageRating} out of 5">
          ${renderStars(product.averageRating)} ${product.averageRating} (${product.reviews})
        </div>

        <div class="price-row">
          <span class="current-price">${formatPrice(product.currentPrice)}</span>
          <span class="rrp">${formatPrice(product.rrp)}</span>
        </div>

        ${
          product.onSale
            ? `<div class="saving">Save ${formatPrice(savings)}</div>`
            : `<div class="saving" style="visibility:hidden;">No saving</div>`
        }

        <div class="product-cta">
          <button class="product-btn" type="button">View Product</button>
        </div>
      </div>
    </article>
  `;
}

function renderFeaturedProducts() {
  const container = document.getElementById("featured-products");
  if (!container || !Array.isArray(featuredProducts)) return;

  container.innerHTML = featuredProducts
    .map((product) => createProductCard(product))
    .join("");
}

function appendMessage(role, text) {
  const chatMessages = document.getElementById("chat-messages");
  if (!chatMessages) return;

  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessageToBackend(message) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error("Backend request failed.");
  }

  return response.json();
}

function initChatDrawer() {
  const chatToggle = document.getElementById("chat-toggle");
  const chatPanel = document.getElementById("chat-panel");
  const chatClose = document.getElementById("chat-close");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");

  if (!chatToggle || !chatPanel || !chatClose || !chatForm || !chatInput) return;

  function openChat() {
    chatPanel.classList.add("open");
    chatPanel.setAttribute("aria-hidden", "false");
    chatToggle.setAttribute("aria-expanded", "true");
    chatInput.focus();
  }

  function closeChat() {
    chatPanel.classList.remove("open");
    chatPanel.setAttribute("aria-hidden", "true");
    chatToggle.setAttribute("aria-expanded", "false");
  }

  chatToggle.addEventListener("click", () => {
    const isOpen = chatPanel.classList.contains("open");
    if (isOpen) {
      closeChat();
    } else {
      openChat();
    }
  });

  chatClose.addEventListener("click", closeChat);

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const userText = chatInput.value.trim();
    if (!userText) return;

    appendMessage("user", userText);
    chatInput.value = "";

    appendMessage("assistant", "Thinking...");

    const chatMessages = document.getElementById("chat-messages");
    const thinkingBubble = chatMessages.lastElementChild;

    try {
      const data = await sendMessageToBackend(userText);
      thinkingBubble.textContent = data.reply;
    } catch (error) {
      thinkingBubble.textContent =
        "Sorry — the chatbot backend is not responding right now.";
      console.error(error);
    }
  });
}

function initDisclaimerModal() {
  const modal = document.getElementById("disclaimer-modal");
  const acceptBtn = document.getElementById("disclaimer-accept");

  if (!modal || !acceptBtn) return;

  acceptBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  renderFeaturedProducts();
  initChatDrawer();
  initDisclaimerModal();
});
