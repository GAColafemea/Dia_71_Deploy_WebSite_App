from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from flask import abort


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)
login_manager = LoginManager()   #flask login documentation
login_manager.init_app(app)  #flask login documentation

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#Create admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function



@login_manager.user_loader  #flask login documentation
def load_user(user_id):  #flask login documentation
    print(user_id, "legal")
    return User.query.get(int(user_id))   #está diferente da documentação.. Precisa do query para pegar do banco de dados.

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('get_all_posts'))

##CONFIGURE TABLES

class User(UserMixin, db.Model): #tabela pai(one)
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    posts = relationship("BlogPost", back_populates="author") #não aparece no banco de dados. Classe/campo do filho
    comments = relationship("Comment", back_populates="comment_author") #não aparece no banco de dados Classe/campo do filho


class BlogPost(db.Model): # tabela filha (many)
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id")) #chave externa tabela Pai.(many)
    author = relationship("User", back_populates="posts") #não aparece no banco de dados. Classe e campo da tabela pai.
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # ***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post") #não aparece no banco de dados


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id")) #chave externa tabela Pai.(many)
    comment_author = relationship("User", back_populates="comments") #não aparece no banco de dados

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))  #chave externa tabela Pai.(many)
    parent_post = relationship("BlogPost", back_populates="comments") #não aparece no banco de dados
    text = db.Column(db.Text, nullable=False)


# db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


@app.route('/register', methods=["GET","POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        if request.method == "POST":

            if User.query.filter_by(email=register_form.email.data).first():
                # User already exists
                flash("You've already signed up with that email, log in instead!")
                return redirect(url_for('get_all_posts'))


            hash_salt_pwd = generate_password_hash(
                register_form.password.data,
                method='pbkdf2:sha256',
                salt_length=8
            )
            new_user = User(
                email = register_form.email.data,
                password = hash_salt_pwd,
                name = register_form.name.data
            )  #forma diferente de pegar o formulário da aula 63
            db.session.add(new_user)
            db.session.commit()

            #log in e autenticar o user depois de adicioná-lo ao DB
            login_user(new_user)

            # logged_in = current_user.is_authenticated
            return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated )



@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if current_user.is_authenticated:
        return redirect(url_for('get_all_posts'))
    else:
        if request.method == "POST":
            email = login_form.email.data
            password = login_form.password.data

            #encontrar o user no Banco de Dados para ver se existe e se é válido

            user = User.query.filter_by(email=email).first()
            # print(user)
            # print(user.password)
            # Email doesn't exist
            if not user:
                flash("That email does not exist, please try again.")
                return redirect(url_for('login'))
            # Password incorrect

            elif not check_password_hash(user.password, password):
                flash('Password incorrect, please try again.')
                return redirect(url_for('login'))
            # Email exists and password correct
            else:
                login_user(user) #flask está agora com o login do user sendo realizado.User session agora está funcionando.
                flash(f'Login successful for {user.name}.')
                return redirect(url_for('get_all_posts'))

        return render_template("login.html", logged_in=current_user.is_authenticated, form=login_form ,title="Login")


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = BlogPost.query.get(post_id)

    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        comment_form.comment_text.data = ""
    return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated, form=comment_form)


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,  #agora tem que enviar o objeto
            date=date.today().strftime("%B %d, %Y")
        )
        print(current_user.name)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=current_user.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id, logged_in=current_user.is_authenticated))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
