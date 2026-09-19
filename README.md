# 🌾 FarmLink

FarmLink is a full-stack agricultural marketplace that connects **farmers**, **buyers**, and **transporters** in a single platform — from listing produce, to placing and paying for orders, to arranging delivery and releasing payment once goods are received. It's built to cut out middlemen, give farmers direct market access, and give buyers a transparent view of pricing and delivery status from start to finish.

## 🌍 Project Overview

FarmLink is a three-sided marketplace, not just a product catalog:

- **Farmers** list produce, track orders, and receive AI-assisted pricing and demand forecasts based on their own sales history.
- **Buyers** browse and search listings, manage a cart across multiple farmers, pay via M-Pesa, and track each order from payment through delivery.
- **Transporters** pick up available delivery jobs, manage their vehicles, and get paid once the buyer confirms receipt.

Money moves through the platform on two separate schedules: farmers are paid once a buyer's payment is confirmed, and transporters are paid once the buyer confirms the delivery actually arrived — each tracked through a wallet and an itemized earnings record per user.

## ✨ Core Features

**Marketplace**
- 🛒 Product listing and management, with per-farmer inventory
- 🔍 Search and category filtering
- 🛍️ Multi-farmer shopping cart, with save-for-later support

**Payments**
- 💳 M-Pesa STK Push checkout, confirmed via an asynchronous payment webhook (not the client redirect)
- 👛 Per-user wallets tracking total earned, paid out, and pending payout
- 🧾 Itemized earnings records (product sales, transport fees, commission) per transaction

**Logistics**
- 🚚 Automatic transport job creation once payment is confirmed
- 🧑‍✈️ Transporter dashboard to browse and accept open delivery jobs
- 📍 Vehicle management for transporters
- ⭐ Post-delivery ratings for transporters

**Intelligence**
- 📈 AI-assisted demand forecasting per product, based on recent order history
- 💰 AI-assisted price recommendations based on historical sales and price stability

**Platform**
- 👤 Role-based registration and authentication (Farmer / Buyer / Transporter)
- 🔔 In-app notifications for orders, payments, and deliveries
- 📱 Responsive design (desktop & mobile)
- 🔐 CSRF-protected forms, server-side validation, and a signature-verified payment webhook

## 🛠️ Technology Stack

**Backend**
- Python / Django

**Data & Analytics**
- pandas, NumPy — order history analysis, demand forecasting, price recommendations

**Frontend**
- HTML5, CSS3, Bootstrap 5, JavaScript

**Database**
- SQLite (development) — PostgreSQL recommended for production

**Payments**
- Safaricom M-Pesa Daraja API (STK Push)

**Deployment**
- Render / PythonAnywhere / Railway (Django-compatible hosts)
- ngrok, for exposing the local M-Pesa webhook during development

## 📂 Project Structure

```
farmlink/
├── farmlink/              # Project settings, root URL config
├── accounts/               # Main app: models, views, forms, admin, AI modules
│   ├── ai/                 # demand_forecaster.py, price_recommender.py, product_recommender.py
│   ├── templates/           # Dashboards, Orders, Transport, Ai_Services, Authentication
│   ├── static/
│   ├── models.py
│   ├── views.py
│   ├── admin.py
│   ├── signals.py
│   └── mpesa.py             # M-Pesa STK push integration
├── media/                   # Uploaded product images, profile pictures
├── manage.py
└── requirements.txt
```

## ⚙️ Setup & Installation

**1. Clone the repository**
```bash
git clone https://github.com/<your-username>/farmlink.git
cd farmlink
```

**2. Create and activate a virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Create a `.env` file in the project root:
```
SECRET_KEY=your-django-secret-key
DEBUG=True
MPESA_CONSUMER_KEY=your-mpesa-consumer-key
MPESA_CONSUMER_SECRET=your-mpesa-consumer-secret
MPESA_SHORTCODE=your-shortcode
MPESA_PASSKEY=your-passkey
MPESA_CALLBACK_URL=https://your-ngrok-url.ngrok-free.app/mpesa/callback/
```

**5. Run migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

**6. Create a superuser** (for admin access)
```bash
python manage.py createsuperuser
```

**7. Run the development server**
```bash
python manage.py runserver
```

**8. For local M-Pesa testing**, expose your local server with ngrok and set `MPESA_CALLBACK_URL` to the resulting HTTPS URL — Safaricom's servers cannot reach `localhost` directly:
```bash
ngrok http 8000
```

## 👥 User Roles

| Role | Can do |
|---|---|
| **Farmer** | List and manage products, view incoming orders, see AI price/demand insights, track revenue |
| **Buyer** | Browse products, manage cart, checkout via M-Pesa, track orders and deliveries, confirm receipt, rate transporters |
| **Transporter** | Register vehicles, browse and accept delivery jobs, update delivery status, track earnings |

## 💳 Payment & Payout Flow

1. Buyer checks out — an M-Pesa STK push is sent, and orders are created with `pending` status.
2. Safaricom confirms payment via webhook — orders move to `confirmed`, stock is decremented, and the farmer's wallet is credited.
3. A transport job is created automatically and appears to available transporters.
4. A transporter accepts the job and delivers the order.
5. The buyer confirms receipt — the transporter's wallet is credited and the transport job is closed out.

## 🎯 Objectives

- Digitize agricultural trade from listing to delivery, not just listing to sale
- Give farmers direct market access and data-driven pricing insight
- Make delivery logistics and payment status transparent to every party involved
- Demonstrate full-stack development across marketplace logic, payments integration, and applied data analysis

## 🚀 Future Enhancements

- Real-time messaging between buyers, farmers, and transporters
- Admin analytics dashboard with visual reporting
- Distance-based dynamic transport pricing
- Product rating and review system
- Automated M-Pesa payouts (B2C) instead of manual wallet withdrawal processing

## 🧪 Running Tests

```bash
python manage.py test
```

## 📄 License

This project is licensed under the MIT License — see the `LICENSE` file for details.

## 👨‍💻 Author

**Ibrahim Mwita Mutisia**
Full-Stack Web Developer | Android Developer

📧 [mwitaibrahim88@gmail.com] · 🔗 [Portfolio link:https://mutisiawebsite.pythonanywhere.com/]
