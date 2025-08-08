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

// Product data array (replace or fetch this data from your backend)
const products = [
  {
    image: "https://store.storeimages.cdn-apple.com/4668/as-images.apple.com/is/mbp14-spaceblack-202310?wid=400&hei=300&fmt=jpeg&qlt=95&.v=1697913383882",
    title: 'MacBook Pro 14"',
    desc: 'Apple M3 Pro chip, 18GB RAM, 512GB SSD, Super Retina XDR display, macOS Sonoma, 18-hour battery.',
    price: '$1,999',
    buyLink: '#'
  },
  {
    image: "https://images.dell.com/is/image/DellContent/content/dam/ss2/product-images/dell-client-products/notebooks/xps-notebooks/13-9315-xps/pdp/laptop-xps-13-9315-hero-504x350-ng.psd?fmt=png-alpha&wid=400&hei=300",
    title: 'Dell XPS 13',
    desc: 'Intel Core i7 13th Gen, 16GB RAM, 512GB SSD, InfinityEdge FHD+ touch, 2-year warranty, Windows 11.',
    price: '$1,349',
    buyLink: '#'
  },
  {
    image: "https://cdn.cnetcontent.com/d6/e6/d6e6b22d-28d9-4af5-9431-6a1493f6eaa7.png",
    title: 'ThinkPad X1 Carbon Gen 11',
    desc: 'Ultra-light, 14" 2.8K OLED, Intel Evo i7, 32GB RAM, 1TB SSD, RapidCharge, fingerprint unlock.',
    price: '$1,699',
    buyLink: '#'
  },
  {
    image: "https://m.media-amazon.com/images/I/61e4nXyq3TL._AC_SY355_.jpg",
    title: 'HP Spectre x360',
    desc: 'Convertible 2-in-1, 13.5" OLED Touch, Intel i7 14-core, 16GB RAM, 1TB SSD, WiFi 6E, Stylus included.',
    price: '$1,499',
    buyLink: '#'
  },
  {
    image: "https://images.samsung.com/is/image/samsung/p6pim/in/np930xfg-kc2inb/gallery/in-galaxy-book4-pro-16inch-np930xfg-kc2inb-thumb-539802999?$400_300_PNG$",
    title: 'Samsung Galaxy Book4 Pro',
    desc: '16" AMOLED, Intel Core Ultra, dedicated Intel graphics, S-Pen support, ultra-slim, 120Hz refresh.',
    price: '$1,699',
    buyLink: '#'
  }
];

// Reference to product grid container
const productGrid = document.getElementById('productGrid');

function renderProducts(productsArr) {
  productGrid.innerHTML = ''; // Clear existing

  productsArr.forEach(product => {
    const card = document.createElement('div');
    card.className = 'product-card';

    card.innerHTML = `
      <div class="product-image">
        <img src="${product.image}" alt="${product.title}" />
      </div>
      <div class="product-content">
        <h3>${product.title}</h3>
        <p class="desc">${product.desc}</p>
        <div class="price-row">
          <span class="price">${product.price}</span>
          <a href="#" class="buy-btn" tabindex="0" aria-label="Buy ${product.title}">Enquiry</a>
        </div>
      </div>
    `;

    // Attach click events to both card and button
    card.addEventListener('click', () => showProductModal(product));
    card.querySelector('.buy-btn').addEventListener('click', (e) => {
      e.preventDefault();
      showProductModal(product);
    });

    productGrid.appendChild(card);
  });
}


  // Attach click listeners to all enquiry buttons
  document.querySelectorAll('.enquiry-btn').forEach(button => {
    button.addEventListener('click', (e) => {
      const index = e.target.getAttribute('data-index');
      showProductModal(productsArr[index]);
    });
  });



// Initial render of all products
renderProducts(products);

// Search functionality for product filtering
const searchInput = document.getElementById('productSearch');
if (searchInput) {
  searchInput.addEventListener('input', () => {
    const query = searchInput.value.trim().toLowerCase();

    const filteredProducts = products.filter(product =>
      product.title.toLowerCase().includes(query) || product.desc.toLowerCase().includes(query)
    );

    renderProducts(filteredProducts);
  });
}

function showProductModal(product) {
  // Create backdrop div
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';

  // Modal content container
  const modal = document.createElement('div');
  modal.className = 'modal-content';

  // Close button
  const closeBtn = document.createElement('button');
  closeBtn.className = 'modal-close';
  closeBtn.innerHTML = '&times;';
  closeBtn.setAttribute('aria-label', 'Close modal');
  closeBtn.onclick = () => document.body.removeChild(backdrop);

  // Modal inner HTML with product details
  modal.innerHTML = `
    <h2>${product.title}</h2>
    <img src="${product.image}" alt="${product.title}" />
    <p>${product.desc}</p>
    <p class="modal-price">${product.price}</p>
    <button class="modal-buy-btn">Add to Cart</button>
  `;

  modal.prepend(closeBtn);
  backdrop.appendChild(modal);

  // Close modal if clicked outside modal-content
  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) {
      document.body.removeChild(backdrop);
    }
  });

  // Append modal to body
  document.body.appendChild(backdrop);
}


