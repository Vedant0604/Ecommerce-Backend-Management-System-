import streamlit as st
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import bcrypt
import uuid

DATABASE_URL = "sqlite:///ecommerce.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default='user')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    # The 'accounts' relationship has been removed as it was for banking, not e-commerce


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CartItem(Base):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer, default=1)
    # Relationships will be defined later


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_uid = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    total_amount = Column(Float, nullable=False)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.now)
    # Relationships will be defined later


class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer, nullable=False)
    price_at_purchase = Column(Float, nullable=False)
    # Relationships will be defined later


# Define relationships after all classes are declared
def _define_relationships():
    # User.accounts relationship removed
    # Account class and its relationships removed

    CartItem.product = relationship("Product")
    CartItem.user = relationship("User")

    Order.user = relationship("User")
    Order.items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    OrderItem.order = relationship("Order", back_populates="items")
    OrderItem.product = relationship("Product")


# Call this function immediately after all classes are defined
_define_relationships()


def init_db():
    Base.metadata.create_all(engine)


@st.cache_resource
def get_session():
    return Session()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


def register_user(username, password, role='user'):
    session = get_session()
    try:
        if session.query(User).filter_by(username=username).first():
            return False, "Username already exists."
        hashed_password = hash_password(password)
        new_user = User(username=username, password_hash=hashed_password, role=role)
        session.add(new_user)
        session.commit()
        return True, "Registration successful."
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def login_user(username, password):
    session = get_session()
    try:
        user = session.query(User).filter_by(username=username, is_active=True).first()
        if user and check_password(password, user.password_hash):
            return user, "Login successful."
        elif user and not user.is_active:
            return None, "Account is inactive."
        else:
            return None, "Invalid username or password."
    except SQLAlchemyError as e:
        return None, f"Database error: {e}"
    finally:
        session.close()


def add_product(name, description, price, stock):
    session = get_session()
    try:
        new_product = Product(name=name, description=description, price=price, stock=stock)
        session.add(new_product)
        session.commit()
        return True, "Product added successfully."
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def get_all_products():
    session = get_session()
    try:
        products = session.query(Product).all()
        return products
    finally:
        session.close()


def get_product_by_id(product_id):
    session = get_session()
    try:
        product = session.query(Product).filter_by(id=product_id).first()
        return product
    finally:
        session.close()


def update_product_stock(product_id, quantity_change):
    session = get_session()
    try:
        product = session.query(Product).filter_by(id=product_id).first()
        if product:
            product.stock += quantity_change
            session.commit()
            return True
        return False
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()


def add_to_cart(user_id, product_id, quantity):
    session = get_session()
    try:
        cart_item = session.query(CartItem).filter_by(user_id=user_id, product_id=product_id).first()
        product = session.query(Product).filter_by(id=product_id).first()
        if not product or product.stock < quantity:
            return False, "Not enough stock."

        if cart_item:
            if product.stock < (cart_item.quantity + quantity):
                return False, "Not enough stock for additional quantity."
            cart_item.quantity += quantity
        else:
            new_cart_item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
            session.add(new_cart_item)
        session.commit()
        return True, "Product added to cart."
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def get_user_cart(user_id):
    session = get_session()
    try:
        cart_items = session.query(CartItem).filter_by(user_id=user_id).options(
            sqlalchemy.orm.joinedload(CartItem.product)).all()
        return cart_items
    finally:
        session.close()


def remove_from_cart(cart_item_id):
    session = get_session()
    try:
        cart_item = session.query(CartItem).filter_by(id=cart_item_id).first()
        if cart_item:
            session.delete(cart_item)
            session.commit()
            return True, "Item removed from cart."
        return False, "Item not found in cart."
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def place_order(user_id):
    session = get_session()
    try:
        cart_items = session.query(CartItem).filter_by(user_id=user_id).options(
            sqlalchemy.orm.joinedload(CartItem.product)).all()
        if not cart_items:
            return False, "Cart is empty."

        total_amount = 0
        order_items = []
        products_to_update = []

        for item in cart_items:
            product = item.product
            if product.stock < item.quantity:
                session.rollback()
                return False, f"Not enough stock for {product.name}. Available: {product.stock}"
            total_amount += product.price * item.quantity
            order_items.append(
                OrderItem(product_id=product.id, quantity=item.quantity, price_at_purchase=product.price))
            products_to_update.append((product, item.quantity))

        order_uid = str(uuid.uuid4())
        new_order = Order(user_id=user_id, total_amount=total_amount, order_uid=order_uid, status='pending')
        new_order.items.extend(order_items)
        session.add(new_order)

        for product, quantity in products_to_update:
            product.stock -= quantity
            session.add(product)

        for item in cart_items:
            session.delete(item)

        session.commit()
        return True, f"Order {order_uid} placed successfully. Total: {total_amount:.2f}"
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    except Exception as e:
        session.rollback()
        return False, f"An unexpected error occurred: {e}"
    finally:
        session.close()


def get_user_orders(user_id):
    session = get_session()
    try:
        orders = session.query(Order).filter_by(user_id=user_id).options(
            sqlalchemy.orm.joinedload(Order.items).joinedload(OrderItem.product)).order_by(
            Order.created_at.desc()).all()
        return orders
    finally:
        session.close()


def get_all_users():
    session = get_session()
    try:
        users = session.query(User).all()
        return users
    finally:
        session.close()


def toggle_user_status(user_id):
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.is_active = not user.is_active
            session.commit()
            return True, f"User {user.username} status toggled to {user.is_active}."
        return False, "User not found."
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def get_all_orders():
    session = get_session()
    try:
        orders = session.query(Order).options(sqlalchemy.orm.joinedload(Order.user),
                                              sqlalchemy.orm.joinedload(Order.items).joinedload(
                                                  OrderItem.product)).order_by(Order.created_at.desc()).all()
        return orders
    finally:
        session.close()


def update_order_status(order_id, new_status):
    session = get_session()
    try:
        order = session.query(Order).filter_by(id=order_id).first()
        if order:
            order.status = new_status
            session.commit()
            return True, f"Order {order.order_uid} status updated to {new_status}."
        return False, "Order not found."
    except SQLAlchemyError as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def main():
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None

    def logout():
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.success("Logged out successfully.")

    if not st.session_state.logged_in:
        st.title("E-commerce Backend Engine")
        st.subheader("Login / Register")

        menu = ["Login", "Register"]
        choice = st.sidebar.selectbox("Menu", menu)

        if choice == "Login":
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                user, message = login_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user.id
                    st.session_state.username = user.username
                    st.session_state.role = user.role
                    st.success(message)
                    st.rerun()  # Changed from st.experimental_rerun()
                else:
                    st.error(message)
        elif choice == "Register":
            st.subheader("Register New User")
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            if st.button("Register"):
                success, message = register_user(new_username, new_password)
                if success:
                    st.success(message + " You can now log in.")
                else:
                    st.error(message)
    else:
        st.sidebar.title(f"Welcome, {st.session_state.username} ({st.session_state.role})")
        st.sidebar.button("Logout", on_click=logout)

        if st.session_state.role == 'admin':
            admin_menu = ["Dashboard", "Manage Products", "Manage Users", "View All Orders"]
            admin_choice = st.sidebar.selectbox("Admin Menu", admin_menu)

            if admin_choice == "Dashboard":
                st.title("Admin Dashboard")
                st.write("Overview of the system.")

            elif admin_choice == "Manage Products":
                st.title("Manage Products")
                with st.expander("Add New Product"):
                    p_name = st.text_input("Product Name")
                    p_description = st.text_area("Description")
                    p_price = st.number_input("Price", min_value=0.01, format="%.2f")
                    p_stock = st.number_input("Stock", min_value=0, step=1)
                    if st.button("Add Product"):
                        success, message = add_product(p_name, p_description, p_price, p_stock)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                st.subheader("Existing Products")
                products = get_all_products()
                if products:
                    for product in products:
                        col1, col2, col3, col4, col5 = st.columns([2, 3, 1, 1, 1])
                        col1.write(product.name)
                        col2.write(product.description)
                        col3.write(f"${product.price:.2f}")
                        col4.write(f"Stock: {product.stock}")
                        with col5:
                            st.button("Edit", key=f"edit_prod_{product.id}")
                else:
                    st.info("No products found.")

            elif admin_choice == "Manage Users":
                st.title("Manage Users")
                users = get_all_users()
                if users:
                    for user in users:
                        col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])
                        col1.write(f"ID: {user.id}")
                        col2.write(f"Username: {user.username}")
                        col3.write(f"Role: {user.role}")
                        col4.write(f"Active: {user.is_active}")
                        with col5:
                            if st.button(f"Toggle {'Deactivate' if user.is_active else 'Activate'}",
                                         key=f"toggle_{user.id}"):
                                success, message = toggle_user_status(user.id)
                                if success:
                                    st.success(message)
                                    st.rerun()  # Changed from st.experimental_rerun()
                                else:
                                    st.error(message)
                else:
                    st.info("No users found.")

            elif admin_choice == "View All Orders":
                st.title("All System Orders")
                orders = get_all_orders()
                if orders:
                    for order in orders:
                        st.subheader(f"Order ID: {order.order_uid} (User: {order.user.username})")
                        st.write(
                            f"Total: ${order.total_amount:.2f} | Status: {order.status} | Placed: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write("Items:")
                        for item in order.items:
                            st.write(f"- {item.product.name} x {item.quantity} @ ${item.price_at_purchase:.2f} each")
                        new_status = st.selectbox(f"Change Status for {order.order_uid}",
                                                  ['pending', 'processing', 'shipped', 'delivered', 'cancelled'],
                                                  index=['pending', 'processing', 'shipped', 'delivered',
                                                         'cancelled'].index(order.status), key=f"status_{order.id}")
                        if new_status != order.status:
                            success, message = update_order_status(order.id, new_status)
                            if success:
                                st.success(message)
                                st.rerun()  # Changed from st.experimental_rerun()
                            else:
                                st.error(message)
                        st.markdown("---")
                else:
                    st.info("No orders found.")

        elif st.session_state.role == 'user':
            user_menu = ["Product Listings", "My Cart", "My Orders"]
            user_choice = st.sidebar.selectbox("User Menu", user_menu)

            if user_choice == "Product Listings":
                st.title("Product Listings")
                products = get_all_products()
                if products:
                    for product in products:
                        col1, col2, col3, col4, col5 = st.columns([2, 3, 1, 1, 1])
                        col1.write(product.name)
                        col2.write(product.description)
                        col3.write(f"${product.price:.2f}")
                        col4.write(f"Stock: {product.stock}")
                        if product.stock > 0:
                            with col5:
                                quantity_to_add = st.number_input("Qty", min_value=1, max_value=product.stock, value=1,
                                                                  key=f"qty_{product.id}")
                                if st.button("Add to Cart", key=f"add_cart_{product.id}"):
                                    success, message = add_to_cart(st.session_state.user_id, product.id,
                                                                   quantity_to_add)
                                    if success:
                                        st.success(message)
                                    else:
                                        st.error(message)
                        else:
                            col5.write("Out of Stock")
                else:
                    st.info("No products available.")

            elif user_choice == "My Cart":
                st.title("My Cart")
                cart_items = get_user_cart(st.session_state.user_id)
                if cart_items:
                    total_cart_amount = 0
                    for item in cart_items:
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        col1.write(item.product.name)
                        col2.write(f"Qty: {item.quantity}")
                        item_total = item.quantity * item.product.price
                        total_cart_amount += item_total
                        col3.write(f"${item_total:.2f}")
                        with col4:
                            if st.button("Remove", key=f"remove_cart_{item.id}"):
                                success, message = remove_from_cart(item.id)
                                if success:
                                    st.success(message)
                                    st.rerun()  # Changed from st.experimental_rerun()
                                else:
                                    st.error(message)
                    st.subheader(f"Total Cart Value: ${total_cart_amount:.2f}")
                    if st.button("Place Order"):
                        success, message = place_order(st.session_state.user_id)
                        if success:
                            st.success(message)
                            st.rerun()  # Changed from st.experimental_rerun()
                        else:
                            st.error(message)
                else:
                    st.info("Your cart is empty.")

            elif user_choice == "My Orders":
                st.title("My Orders")
                orders = get_user_orders(st.session_state.user_id)
                if orders:
                    for order in orders:
                        st.subheader(f"Order ID: {order.order_uid}")
                        st.write(
                            f"Total: ${order.total_amount:.2f} | Status: {order.status} | Placed: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write("Items:")
                        for item in order.items:
                            st.write(f"- {item.product.name} x {item.quantity} @ ${item.price_at_purchase:.2f} each")
                        st.markdown("---")
                else:
                    st.info("You have no past orders.")
        else:
            st.error("Unknown user role. Please log in again.")


if __name__ == "__main__":
    main()
