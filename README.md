# Puoric

## Project layout

- `app.py` and `config.py`: application startup and configuration
- `database/`: database setup and models
- `routes/`: Flask routes
- `services/`: shared application data and services
- `templates/`: page templates, shared components, and page sections
- `static/css/`: site styles, theme variables, and responsive rules
- `static/js/`: browser scripts
- `static/images/`: site images
- `instance/`: local application data

## Setup

Create a virtual environment, install dependencies with `pip install -r requirements.txt`, and copy `.env.example` to a private `.env`. Set a stable, randomly generated `SECRET_KEY` before deployment; configure `UPI_PAYEE_ID`, `UPI_PAYEE_NAME`, and the public `STORE_*` contact values if needed. Never commit `.env`, databases, uploaded files, or private customer/admin data. Keep `FLASK_DEBUG=false` outside local development. Start locally with `python app.py` and open `http://127.0.0.1:5000`. The app creates its ignored `instance/` database directory on startup.

Run the test suite with `python -m unittest discover -s tests`. For deployment, use a production WSGI server rather than Flask's built-in development server, and set `SESSION_COOKIE_SECURE=true` when serving over HTTPS. The first admin can create an account from the admin sign-in page; after setup, signed-in admins can add accounts from the dashboard. To allow invitation-based public admin registration, set `ADMIN_SIGNUP_KEY` and share it privately with administrators.

## Store and dashboards

- `/products/`: client catalogue, category filtering, and product details
- `/client/signup` and `/client/login`: client account access
- `/client/dashboard`: addresses, cart, order history, and order tracking
- `/client/profile`: personal details used for the client's beauty profile
- `/admin/signup` and `/admin/login`: separate admin account access
- `/admin/dashboard`: catalogue and order management
- `/admin/customers`: filter, sort, and group clients by profile and order metrics
- `/admin/promotions`: create, edit, and pause automatic client offers

Admins create uniquely named categories and products, including characteristic tags and stock/price options, and can activate or deactivate categories, products, and individual product options. Categories are listed alphabetically. Each product option is unique by its type and value; price does not distinguish duplicate options. A measuring unit is available only for the Weight type. From **Admin dashboard → Store settings**, admins configure the store UPI ID, ship-from state and country, regional shipping fees, and an optional free-shipping merchandise-subtotal threshold. An address in the ship-from state uses the within-state fee; another address in the same country uses the within-country fee; all others use the international fee. Shipping and thresholds use whole rupees; the free-shipping threshold is checked before discounts. Admins can segment clients by minimum age, gender, new/returning status, minimum completed order count, and minimum lifetime spend, and can optionally require a minimum merchandise subtotal for the current order on each offer. This order threshold is checked before discounts and shipping. Every offer requires a start time and may have an optional end time. Offers can target all products and varieties, selected categories, or selected products (including every variety of each selected product). The largest eligible offer is applied at checkout and saved with the order. Festival is a campaign label governed by the offer's active dates.

Clients can edit their profile, save delivery addresses, add products to the cart, pay in advance using UPI QR, and follow order progress. There is no cash-on-delivery option. Shipping is calculated from the selected address; clients can see the fee before placing the order. The order-specific QR pre-fills the store, exact order total including shipping, currency, and order reference. UPI apps may still allow the payer to edit QR details; a static QR cannot enforce locked fields, so use a payment provider's checkout/collect flow if edits must be technically prevented. The client pays by UPI and the order remains Pending until an admin verifies payment. An order cannot be confirmed or shipped before payment is verified. Order progress is Pending → Confirmed → Packed → Shipped; after shipping, the admin can open a prefilled WhatsApp shipment update to the client, review it, and tap Send. When the client receives and checks the correct order, they confirm receipt on the order page, which marks it Delivered/Received. WhatsApp messages are never sent automatically. There is no OTP. Cancelling an undispatched order removes its shipping fee; if already paid, the admin sees the resulting refund due and must process the refund through UPI before recording the refund status. Cancellation after dispatch retains the shipping charge; refunds are handled manually through UPI. After checkout, the order page also offers a prefilled WhatsApp message to the store number in `services/site_data.py`. The client reviews the message and taps Send in WhatsApp; the website does not send it automatically. An admin can save the store UPI ID on the Store settings page; alternatively, `UPI_PAYEE_ID` in `.env` is used until the admin saves a dashboard value. Client/admin sign-in and sign-up choices are shown only when signed out. Admin accounts cannot use the shopping cart. An email address can be used by only one account role for new registrations and email changes. Startup migrations preserve existing accounts and orders, including any pre-existing cross-role email conflicts.