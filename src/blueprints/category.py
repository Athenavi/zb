from flask import Blueprint

from flask import render_template, request, jsonify, flash, redirect, url_for
from src.models import db
from src.models import Category, CategorySubscription
from src.user.authz.decorators import jwt_required, admin_required

category_bp = Blueprint('category', __name__, url_prefix='/category')


@category_bp.route('/', methods=['GET'])
# 分类列表页面
@jwt_required
def category_list(user_id):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 12

        # 获取所有分类
        categories = Category.query.order_by(Category.name.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 获取用户已订阅的分类ID
        subscribed_ids = set()
        subscriptions = CategorySubscription.query.filter_by(
            subscriber_id=user_id
        ).all()
        subscribed_ids = {sub.category_id for sub in subscriptions}

        return render_template('categories/list.html',
                               categories=categories,
                               subscribed_ids=subscribed_ids)
    except Exception as e:
        print(e)


@category_bp.route('/subscribe', methods=['POST'])
# 订阅分类
@jwt_required
def subscribe_category(user_id):
    category_id = request.form.get('category_id', type=int)

    if not category_id:
        return jsonify({'success': False, 'message': '分类ID不能为空'})

    category = Category.query.get_or_404(category_id)

    # 检查是否已经订阅
    existing_subscription = CategorySubscription.query.filter_by(
        subscriber_id=user_id,
        category_id=category_id
    ).first()

    if existing_subscription:
        return jsonify({'success': False, 'message': '您已经订阅了该分类'})

    # 创建新订阅
    subscription = CategorySubscription(
        subscriber_id=user_id,
        category_id=category_id
    )

    db.session.add(subscription)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'成功订阅分类: {category.name}'
    })


# 取消订阅
@category_bp.route('/unsubscribe', methods=['POST'])
@jwt_required
def unsubscribe_category(user_id):
    category_id = request.form.get('category_id', type=int)

    if not category_id:
        return jsonify({'success': False, 'message': '分类ID不能为空'})

    subscription = CategorySubscription.query.filter_by(
        subscriber_id=user_id,
        category_id=category_id
    ).first()

    if not subscription:
        return jsonify({'success': False, 'message': '您未订阅该分类'})

    db.session.delete(subscription)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '取消订阅成功'
    })


@category_bp.route('/add', methods=['GET', 'POST'])
# 添加分类（管理员功能）
@admin_required
def add_category(user_id):
    if request.method == 'POST':
        name = request.form.get('name', '').strip()

        if not name:
            flash('分类名称不能为空', 'error')
            return render_template('categories/add.html')

        # 检查分类是否已存在
        existing_category = Category.query.filter_by(name=name).first()
        if existing_category:
            flash('分类名称已存在', 'error')
            return render_template('categories/add.html')

        category = Category(name=name)
        db.session.add(category)
        db.session.commit()

        flash(f'分类 "{name}" 创建成功', 'success')
        return redirect(url_for('category.category_list'))

    return render_template('categories/add.html')
