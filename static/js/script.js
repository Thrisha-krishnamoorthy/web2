// Sidebar toggle functionality
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');

if (sidebar && sidebarToggle) {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('active');
  });

  window.addEventListener('click', (event) => {
    const clickInsideSidebar = sidebar.contains(event.target);
    const clickOnToggle = sidebarToggle.contains(event.target);
    if (sidebar.classList.contains('active') && !clickInsideSidebar && !clickOnToggle) {
      sidebar.classList.remove('active');
    }
  });
}

// Navbar shadow effect on scroll
const navbar = document.querySelector('.navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    if (window.scrollY > 38) {
      navbar.style.boxShadow = '0 4px 32px rgba(20, 20, 20, 0.13)';
    } else {
      navbar.style.boxShadow = '0 2px 16px rgba(20, 20, 20, 0.04)';
    }
  });
}

// Function to render products
function renderProducts(products) {
  const productGrid = document.getElementById('productGrid');
  if (!productGrid) return;

  productGrid.innerHTML = ''; // Clear existing products

  products.forEach((product, index) => {
    const productCard = document.createElement('div');
    productCard.className = 'product-card';
    productCard.innerHTML = `
      <div class="product-image">
        <img src="${product.image}" alt="${product.title}" />
      </div>
      <div class="product-content">
        <h3>${product.title}</h3>
        <p class="desc">${product.desc}</p>
        <div class="price-row">
          <span class="price">${product.price}</span>
          <button class="buy-btn" onclick="showProductModal(${index})">Enquiry</button>
        </div>
      </div>
    `;
    productGrid.appendChild(productCard);
  });
}

// Show product modal
function showProductModal(index) {
  const products = window.products || [];
  if (!products[index]) return;
  
  const product = products[index];
  const modal = document.getElementById('productModal');
  const modalImage = document.getElementById('modalImage');
  const modalTitle = document.getElementById('modalTitle');
  const modalDesc = document.getElementById('modalDesc');
  const modalPrice = document.getElementById('modalPrice');

  if (modal && modalImage && modalTitle && modalDesc && modalPrice) {
    modalImage.src = product.image;
    modalImage.alt = product.title;
    modalTitle.textContent = product.title;
    modalDesc.textContent = product.desc;
    modalPrice.textContent = product.price;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

// Close modal functionality
const modalClose = document.getElementById('modalClose');
const productModal = document.getElementById('productModal');

if (modalClose && productModal) {
  modalClose.addEventListener('click', () => {
    productModal.style.display = 'none';
    document.body.style.overflow = 'auto';
  });

  // Close modal when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === productModal) {
      productModal.style.display = 'none';
      document.body.style.overflow = 'auto';
    }
  });

  // Close with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && productModal.style.display === 'flex') {
      productModal.style.display = 'none';
      document.body.style.overflow = 'auto';
    }
  });
}

// Initialize products from window.products if available
if (window.products && Array.isArray(window.products)) {
  renderProducts(window.products);
}
