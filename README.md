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

Create a virtual environment, install dependencies with `pip install -r requirements.txt`, and copy `.env.example` to a private `.env`. Set a stable, randomly generated `SECRET_KEY` before deployment; configure `UPI_PAYEE_ID` and `UPI_PAYEE_NAME` if needed. Never commit `.env`. Start locally with `python app.py` and open `http://127.0.0.1:5000`. The app creates its ignored `instance/` database directory on startup.

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

Admins create uniquely named categories and products, including characteristic tags and stock/price options, and can activate or deactivate categories, products, and individual product options. Each product option is unique by its type and value; price does not distinguish duplicate options. A measuring unit is available only for the Weight type. Admins can configure the store UPI ID from **Admin dashboard → Store settings**; the saved ID enables checkout QR payments. Admins can segment clients by age, gender, new/returning status, order count, and spend, then define date-bounded percentage or fixed-amount offers for qualifying clients. Offer creation lets admins select audience features first, then enter the relevant values. An offer can target all categories or selected categories; the largest eligible offer is applied at checkout and its discount is saved with the order. Festival is a campaign label governed by the offer's active dates.

Clients can edit their profile, save delivery addresses, add products to the cart, place cash-on-delivery or UPI QR orders, and follow order progress. After checkout, the order page opens a prefilled WhatsApp message addressed to the store WhatsApp number in `services/site_data.py`. The message contains the order reference, client and delivery contacts, address, items, subtotal, discounts, total, and payment details. The client reviews the message and taps Send in WhatsApp; the website does not send it automatically. An admin can save the store UPI ID on the Store settings page; alternatively, `UPI_PAYEE_ID` in `.env` is used until the admin saves a dashboard value. The order-specific QR pre-fills the store, exact order total, currency, and order reference. UPI apps may still allow the payer to edit QR details; a static QR cannot enforce locked fields, so use a payment provider's checkout/collect flow if edits must be technically prevented. UPI payments remain pending until an admin verifies them in order management. Order progress uses one sequence: Pending → Confirmed → Packed → Shipped → Delivered, with Cancelled available before delivery. The admin selects only the current or next valid step; shipping status follows order status, so the admin does not update duplicate progress fields. For all payment methods, marking an order Shipped prepares a six-digit, 24-hour receipt code and a WhatsApp message addressed to the client's delivery phone. The admin opens the prefilled chat and taps Send; WhatsApp does not send automatically. The client shares the code only after receiving and checking the correct order. For COD, collect the full amount before the client shares the code; code verification marks delivery and payment as confirmed. For UPI, code verification confirms receipt only and does not change payment status. Five incorrect attempts require a new code. WhatsApp must be installed or available in the admin's browser, and the client's delivery phone must be valid for WhatsApp. Client/admin sign-in and sign-up choices are shown only when signed out. Admin accounts cannot use the shopping cart. An email address can be used by only one account role for new registrations and email changes. Startup migrations preserve existing accounts and orders, including any pre-existing cross-role email conflicts.