from datetime import date
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from forms import CreatePostForm, RegisterUserForm, LoginUserForm, CommentForm

import os
from dotenv import load_dotenv
load_dotenv('.env')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('APP_SECRET_KEY', '12345')
ckeditor = CKEditor(app)
Bootstrap(app)

# #CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
# SQLAlchemy 1.4 removed the deprecated postgres dialect name, the name postgresql must be used instead now.
# The dialect is the part before the :// in the URL.
# SQLAlchemy 1.3 and earlier showed a deprecation warning but still accepted it.
# To fix this, rename postgres:// in the URL to postgresql://.
heroku_postgres_uri = os.environ.get('DATABASE_URL', 'sqlite:///blog.db')
if heroku_postgres_uri.startswith("postgres://"):
    heroku_postgres_uri = heroku_postgres_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = heroku_postgres_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False,
                    use_ssl=False,
                    base_url=None)


# #CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # ***************Child Relationship*************#
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship('User', back_populates="posts")

    # ***************Parent Relationship*************#
    # This will act like a List of Comments objects attached to each Post.
    # The "post" refers to the comment property in the Comment class.
    comments = relationship('Comment', back_populates="post")


# create user table
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship('BlogPost', back_populates='author')

    # This will act like a List of Comments objects attached to each User.
    # The "author" refers to the author property in the Comment class.
    comments = relationship('Comment', back_populates='author')


# create comment table
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # ***************Child Relationship*************#
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    # Create reference to the User object, the "comments" refers to the comments property in the User class.
    author = relationship('User', back_populates="comments")

    # ***************Child Relationship*************#
    # Create Foreign Key, "users.id" the users refers to the tablename of BlogPost.
    post_id = db.Column(db.Integer, ForeignKey('blog_posts.id'))
    # Create reference to the User object, the "comments" refers to the comments property in the User class.
    post = relationship('BlogPost', back_populates="comments")


db.create_all()

# config flask-login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# Create admin-only decorator
def admin_only(f):
    # this is an option for define decorator inner wrapper
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print('decorator')
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
            # return abort(Response('Hello World'))
        # Otherwise, continue with the route function
        return f(*args, **kwargs)

    return decorated_function


# # Create author-only decorator for edit post
# def author_only(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         print('decorator')
#         if current_user.id != 1:
#             return abort(403)
#         return f(*args, **kwargs)
#
#     return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    for post in posts:
        print(post.__tablename__)
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['get', 'post'])
def register():
    form = RegisterUserForm()
    if form.validate_on_submit():
        if not User.query.filter_by(email=form.email.data).first():
            register_user = User(
                email=form.email.data,
                password=generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=16),
                name=form.name.data
            )
            db.session.add(register_user)
            db.session.commit()
            login_user(register_user)
            return redirect('/')
        else:
            flash('user already registered, log in here')
            return redirect('login')
    return render_template("register.html", form=form)


@app.route('/login', methods=['get', 'post'])
def login():
    form = LoginUserForm()
    if form.validate_on_submit():
        logged_user = User.query.filter_by(email=form.email.data).first()
        if not logged_user:
            flash('email does not exist')
        elif not check_password_hash(logged_user.password, form.password.data):
            flash('password is not correct')
        else:
            login_user(logged_user)
            return redirect('/')
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['get', 'post'])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    # don't need to pass comments to template, retrieve it via {{ post.comments }} in template
    comments = Comment.query.filter_by(post_id=post_id)
    if form.validate_on_submit():
        new_comment = Comment(
            text=form.comment.data,
            author_id=current_user.id,
            post_id=post_id
        )
        db.session.add(new_comment)
        db.session.commit()
    # return render_template("post.html", post=requested_post, form=form, comments=comments)
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=['get', 'post'])
def contact():
    if request.method == 'GET':
        data = request.args
    else:
        data = request.form
    is_completed = True
    error_field = []
    for key, value in data.items():
        if not value:
            is_completed = False
            error_field.append(key)
    if is_completed:
        import smtplib
        my_email = os.environ.get('MY_EMAIL')
        # using app password for 2fa be used google account--https://joequery.me/guides/python-smtp-authenticationerror/
        password = os.environ.get('PASSWORD')
        with smtplib.SMTP("smtp.gmail.com") as connection:
            connection.starttls()
            connection.login(user=my_email, password=password)
            connection.sendmail(
                from_addr=my_email,
                to_addrs=[data['email'], my_email],
                msg=f"Subject:Your message sent from jason-blog-flask website as below is received! 👆\n\n"
                    f"Name: {data['name']} \nemail: {data['email']}"
                    f"\nPhone: {data['phone_number']} "
                    f"\nMessage:{data['message']}".encode("utf-8"))
    return render_template("contact.html", data=data, is_completed=is_completed, error_field=error_field)


@app.route("/new-post", methods=['get', 'post'])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            # author=current_user,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['get', 'post'])
@login_required
# @author_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    # only admin and post owner can edit the post
    if current_user.id != 1 and current_user.id != post.author_id:
        abort(403)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        # post.author_id = current_user.id
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
