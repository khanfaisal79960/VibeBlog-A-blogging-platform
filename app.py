# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import markdown
import os
import json
import uuid
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "glitch_cor"


POSTS_FILE = 'posts.json'
USERS_FILE = 'users.json'


def load_posts():
    """Loads blog posts from the JSON file."""
    if not os.path.exists(POSTS_FILE):
        return []
    try:
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)

            for post in posts_data:
                if 'tags' not in post:
                    post['tags'] = []
            return posts_data
    except json.JSONDecodeError:

        return []

def save_posts(posts):
    """Saves blog posts to the JSON file."""
    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=4)

def load_users():
    """Loads user data from the JSON file."""
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_users(users):
    """Saves user data to the JSON file."""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)

posts = load_posts()
users = load_users()


def login_required(f):
    """Decorator to restrict access to logged-in users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('You need to be logged in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def load_logged_in_user():
    """Loads the user from session before each request."""
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = next((u for u in users if u['id'] == user_id), None)


@app.context_processor
def inject_global_data():
    all_tags = sorted(list(set(tag for post in posts for tag in post.get('tags', []))))
    return {
        'current_year': datetime.now().year,
        'all_tags': all_tags,
        'user': g.user 
    }



@app.route('/')
def index():
    """
    Renders the homepage displaying all blog posts.
    Supports search queries and tag filtering.
    Posts are sorted by creation date, newest first.
    """
    search_query = request.args.get('query', '').strip().lower()
    filter_tag = request.args.get('tag', '').strip().lower()

    filtered_posts = posts

    if search_query:
        filtered_posts = [
            p for p in filtered_posts
            if search_query in p['title'].lower() or search_query in p['content'].lower()
        ]

    if filter_tag:
        filtered_posts = [
            p for p in filtered_posts
            if filter_tag in [t.lower() for t in p.get('tags', [])]
        ]

    
    sorted_posts = sorted(filtered_posts, key=lambda p: p['timestamp'], reverse=True)
    return render_template('index.html', posts=sorted_posts, search_query=search_query, filter_tag=filter_tag)

@app.route('/post/<string:post_id>')
def view_post(post_id):
    """
    Renders a single blog post by its ID.
    Converts Markdown content to HTML before rendering.
    """
    post = next((p for p in posts if p['id'] == post_id), None)
    if post:
        # Convert Markdown content to HTML
        post_content_html = markdown.markdown(post['content'], extensions=['fenced_code', 'tables'])
        return render_template('post.html', post=post, post_content_html=post_content_html)
    flash('Post not found!', 'error')
    return redirect(url_for('index'))

@app.route('/create', methods=['GET', 'POST'])
@login_required 
def create_post():
    """
    Handles the creation of new blog posts.
    GET: Displays the create post form.
    POST: Processes the form submission, saves the new post, and redirects.
    """
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        content = request.form['content']
        image_url = request.form.get('image_url', 'https://placehold.co/800x450/4B0082/FFFFFF?text=VibeBlog+Image')
        tags_input = request.form.get('tags', '').strip()
        tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]

        if not title or not author or not content:
            flash('All fields are required!', 'error')
            return render_template('create.html', title=title, author=author, content=content, image_url=image_url, tags_input=tags_input)

        new_post = {
            'id': str(uuid.uuid4()),
            'title': title,
            'author': author,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'image_url': image_url,
            'tags': tags,
            'user_id': g.user['id'] 
        }
        posts.append(new_post)
        save_posts(posts)
        flash('Post created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/edit/<string:post_id>', methods=['GET', 'POST'])
@login_required 
def edit_post(post_id):
    """
    Handles the editing of existing blog posts.
    GET: Displays the edit post form with current post data.
    POST: Processes the form submission, updates the post, and redirects.
    """
    post = next((p for p in posts if p['id'] == post_id), None)
    if not post:
        flash('Post not found!', 'error')
        return redirect(url_for('index'))

    
    if post.get('user_id') != g.user['id']:
        flash('You are not authorized to edit this post.', 'error')
        return redirect(url_for('view_post', post_id=post_id))

    if request.method == 'POST':
        post['title'] = request.form['title']
        post['author'] = request.form['author']
        post['content'] = request.form['content']
        post['image_url'] = request.form.get('image_url', 'https://placehold.co/800x450/4B0082/FFFFFF?text=VibeBlog+Image')
        tags_input = request.form.get('tags', '').strip()
        post['tags'] = [tag.strip() for tag in tags_input.split(',') if tag.strip()]

        if not post['title'] or not post['author'] or not post['content']:
            flash('All fields are required!', 'error')
            return render_template('edit.html', post=post)

        save_posts(posts)
        flash('Post updated successfully!', 'success')
        return redirect(url_for('view_post', post_id=post['id']))
    
    post['tags_input'] = ', '.join(post.get('tags', []))
    return render_template('edit.html', post=post)

@app.route('/delete/<string:post_id>', methods=['POST'])
@login_required 
def delete_post(post_id):
    """
    Handles the deletion of blog posts.
    """
    global posts
    post_to_delete = next((p for p in posts if p['id'] == post_id), None)

    if not post_to_delete:
        flash('Post not found!', 'error')
        return redirect(url_for('index'))

    
    if post_to_delete.get('user_id') != g.user['id']:
        flash('You are not authorized to delete this post.', 'error')
        return redirect(url_for('view_post', post_id=post_id))

    posts = [p for p in posts if p['id'] != post_id]
    save_posts(posts)
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if g.user: 
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        if not username or not password or not confirm_password:
            flash('All fields are required!', 'error')
            return render_template('register.html', username=username)

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html', username=username)

        if any(u['username'] == username for u in users):
            flash('Username already exists. Please choose a different one.', 'error')
            return render_template('register.html', username=username)

        hashed_password = generate_password_hash(password)
        new_user = {
            'id': str(uuid.uuid4()),
            'username': username,
            'password_hash': hashed_password
        }
        users.append(new_user)
        save_users(users)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if g.user: 
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        user = next((u for u in users if u['username'] == username), None)

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handles user logout."""
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/about')
def about():
    """Renders the About page."""
    return render_template('about.html')

@app.route('/contact')
def contact():
    """Renders the Contact page."""
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)
