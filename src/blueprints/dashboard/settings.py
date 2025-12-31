"""
Dashboard 系统设置模块
包含系统设置、菜单管理、页面管理等功能
"""
import inspect
import json
from datetime import datetime

from flask import request, render_template, jsonify

from src.auth_utils import admin_required
from src.extensions import limiter
from src.models import User, db, Menus, MenuItems, Pages, SystemSettings
from . import admin_bp


@admin_bp.route('/settings', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
@limiter.limit("10 per minute")
def admin_settings(user_id):
    try:
        # 获取当前用户信息
        current_user = db.session.query(User).filter_by(id=user_id).first()

        # 处理系统设置保存
        if request.method == 'POST' and 'settings' in request.form:
            settings_data = request.form.get('settings')
            try:
                settings = json.loads(settings_data)
                for key, value in settings.items():
                    setting = db.session.query(SystemSettings).filter_by(key=key).first()
                    if setting:
                        setting.value = value
                        setting.updated_at = datetime.now()
                        setting.updated_by = user_id
                    else:
                        setting = SystemSettings(
                            key=key,
                            value=value,
                            updated_at=datetime.now(),
                            updated_by=user_id
                        )
                        db.session.add(setting)
                db.session.commit()
                return jsonify({'success': True, 'message': '设置已保存'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'保存失败: {str(e)}'})

        # 处理菜单操作
        if request.method == 'POST' and 'menu_action' in request.form:
            action = request.form.get('menu_action')

            if action == 'create_menu':
                name = request.form.get('name')
                slug = request.form.get('slug')
                description = request.form.get('description', '')

                if not name or not slug:
                    return jsonify({'success': False, 'message': '菜单名称和标识不能为空'})

                existing_menu = db.session.query(Menus).filter_by(slug=slug).first()
                if existing_menu:
                    return jsonify({'success': False, 'message': '菜单标识已存在'})

                menu = Menus(
                    name=name,
                    slug=slug,
                    description=description,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(menu)
                db.session.commit()
                return jsonify({'success': True, 'message': '菜单创建成功', 'menu_id': menu.id})

            elif action == 'update_menu':
                menu_id = request.form.get('menu_id')
                name = request.form.get('name')
                description = request.form.get('description', '')
                is_active = request.form.get('is_active') == 'true'

                menu = db.session.query(Menus).filter_by(id=menu_id).first()
                if menu:
                    menu.name = name
                    menu.description = description
                    menu.is_active = is_active
                    menu.updated_at = datetime.now()
                    db.session.commit()
                    return jsonify({'success': True, 'message': '菜单更新成功'})
                return jsonify({'success': False, 'message': '菜单不存在'})

            elif action == 'delete_menu':
                menu_id = request.form.get('menu_id')
                menu = db.session.query(Menus).filter_by(id=menu_id).first()
                if menu:
                    # 删除菜单项
                    db.session.query(MenuItems).filter_by(menu_id=menu_id).delete()
                    db.session.delete(menu)
                    db.session.commit()
                    return jsonify({'success': True, 'message': '菜单已删除'})
                return jsonify({'success': False, 'message': '菜单不存在'})

        # 处理菜单项操作
        if request.method == 'POST' and 'menu_item_action' in request.form:
            action = request.form.get('menu_item_action')

            if action == 'create_item':
                menu_id = request.form.get('menu_id')
                parent_id = request.form.get('parent_id')
                title = request.form.get('title')
                url = request.form.get('url')
                target = request.form.get('target', '_self')
                order_index = request.form.get('order_index', 0)

                if not title:
                    return jsonify({'success': False, 'message': '菜单项标题不能为空'})

                item = MenuItems(
                    menu_id=menu_id,
                    parent_id=parent_id if parent_id else None,
                    title=title,
                    url=url,
                    target=target,
                    order_index=order_index,
                    created_at=datetime.now()
                )
                db.session.add(item)
                db.session.commit()
                return jsonify({'success': True, 'message': '菜单项创建成功'})

            elif action == 'update_item':
                item_id = request.form.get('item_id')
                title = request.form.get('title')
                url = request.form.get('url')
                target = request.form.get('target', '_self')
                order_index = request.form.get('order_index', 0)
                is_active = request.form.get('is_active') == 'true'

                item = db.session.query(MenuItems).filter_by(id=item_id).first()
                if item:
                    item.title = title
                    item.url = url
                    item.target = target
                    item.order_index = order_index
                    item.is_active = is_active
                    db.session.commit()
                    return jsonify({'success': True, 'message': '菜单项更新成功'})
                return jsonify({'success': False, 'message': '菜单项不存在'})

            elif action == 'delete_item':
                item_id = request.form.get('item_id')
                item = db.session.query(MenuItems).filter_by(id=item_id).first()
                if item:
                    # 检查是否有子项
                    child_count = db.session.query(MenuItems).filter_by(parent_id=item_id).count()
                    if child_count > 0:
                        return jsonify({'success': False, 'message': '请先删除子菜单项'})

                    db.session.delete(item)
                    db.session.commit()
                    return jsonify({'success': True, 'message': '菜单项已删除'})
                return jsonify({'success': False, 'message': '菜单项不存在'})

        # 处理页面操作
        if request.method == 'POST' and 'page_action' in request.form:
            action = request.form.get('page_action')

            if action == 'create_page':
                title = request.form.get('title')
                slug = request.form.get('slug')
                content = request.form.get('content', '')
                excerpt = request.form.get('excerpt', '')
                template = request.form.get('template', 'default')
                status = request.form.get('status', 0, type=int)
                parent_id = request.form.get('parent_id')
                order_index = request.form.get('order_index', 0)
                meta_title = request.form.get('meta_title', '')
                meta_description = request.form.get('meta_description', '')
                meta_keywords = request.form.get('meta_keywords', '')

                if not title or not slug:
                    return jsonify({'success': False, 'message': '页面标题和别名不能为空'})

                existing_page = db.query(Pages).filter_by(slug=slug).first()
                if existing_page:
                    return jsonify({'success': False, 'message': '页面别名已存在'})

                page = Pages(
                    title=title,
                    slug=slug,
                    content=content,
                    excerpt=excerpt,
                    template=template,
                    status=status,
                    author_id=user_id,
                    parent_id=parent_id if parent_id else None,
                    order_index=order_index,
                    meta_title=meta_title,
                    meta_description=meta_description,
                    meta_keywords=meta_keywords,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    published_at=datetime.now() if status == 1 else None
                )
                db.add(page)
                db.commit()
                return jsonify({'success': True, 'message': '页面创建成功', 'page_id': page.id})

            elif action == 'update_page':
                page_id = request.form.get('page_id')
                title = request.form.get('title')
                slug = request.form.get('slug')
                content = request.form.get('content', '')
                excerpt = request.form.get('excerpt', '')
                template = request.form.get('template', 'default')
                status = request.form.get('status', 0, type=int)
                parent_id = request.form.get('parent_id')
                order_index = request.form.get('order_index', 0)
                meta_title = request.form.get('meta_title', '')
                meta_description = request.form.get('meta_description', '')
                meta_keywords = request.form.get('meta_keywords', '')

                page = db.session.query(Pages).filter_by(id=page_id).first()
                if not page:
                    return jsonify({'success': False, 'message': '页面不存在'})

                # 检查别名冲突
                existing_page = db.session.query(Pages).filter(
                    Pages.slug == slug,
                    Pages.id != page_id
                ).first()
                if existing_page:
                    return jsonify({'success': False, 'message': '页面别名已存在'})

                page.title = title
                page.slug = slug
                page.content = content
                page.excerpt = excerpt
                page.template = template
                page.status = status
                page.parent_id = parent_id if parent_id else None
                page.order_index = order_index
                page.meta_title = meta_title
                page.meta_description = meta_description
                page.meta_keywords = meta_keywords
                page.updated_at = datetime.now()

                if status == 1 and not page.published_at:
                    page.published_at = datetime.now()

                db.session.commit()
                return jsonify({'success': True, 'message': '页面更新成功'})

            elif action == 'delete_page':
                page_id = request.form.get('page_id')
                page = db.session.query(Pages).filter_by(id=page_id).first()
                if page:
                    # 检查是否有子页面
                    child_count = db.session.query(Pages).filter_by(parent_id=page_id).count()
                    if child_count > 0:
                        return jsonify({'success': False, 'message': '请先删除子页面'})

                    db.session.delete(page)
                    db.session.commit()
                    return jsonify({'success': True, 'message': '页面已删除'})
                return jsonify({'success': False, 'message': '页面不存在'})

        # GET请求 - 显示设置页面
        # 获取系统设置
        system_settings = db.session.query(SystemSettings).all()
        settings_dict = {setting.key: setting.value for setting in system_settings}

        # 获取菜单
        menus = db.session.query(Menus).order_by(Menus.created_at.desc()).all()

        # 获取所有菜单项并按菜单分组
        menu_items = {}
        for menu in menus:
            items = db.session.query(MenuItems).filter_by(menu_id=menu.id).order_by(MenuItems.order_index).all()
            menu_items[menu.id] = items

        # 获取页面
        pages = db.session.query(Pages).order_by(Pages.created_at.desc()).all()

        return render_template('dashboard/settings.html',
                               settings=settings_dict,
                               menus=menus,
                               menu_items=menu_items,
                               pages=pages,
                               current_user=current_user)

    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        current_func_name = inspect.currentframe().f_code.co_name
        # 输出当前视图名称和操作人ID
        print(f"==>{current_func_name}, User ID: {user_id}")
