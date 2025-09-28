# services/pay/Ali.py
import logging
from datetime import datetime, timedelta

from alipay import AliPay #python-alipay-sdk==3.3.0

from src.models import VIPSubscription, db
from src.setting import AliPayConfig


class AlipayService:
    def __init__(self, app=None):
        self.alipay = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """初始化支付宝支付实例:cite[7]:cite[8]"""
        try:
            self.alipay = AliPay(
                appid=app.config['ALIPAY_APPID'],
                app_notify_url=app.config['ALIPAY_NOTIFY_URL'],
                app_private_key_string=app.config['ALIPAY_PRIVATE_KEY_STRING'],
                alipay_public_key_string=app.config['ALIPAY_PUBLIC_KEY_STRING'],
                sign_type="RSA2",
                debug=app.config['ALIPAY_DEBUG'],
                config=AliPayConfig(timeout=15)  # 设置超时时间
            )
        except Exception as e:
            logging.error(f"初始化支付宝支付失败: {str(e)}")
            raise

    def create_payment(self, vip_subscription, return_url=None):
        """创建支付宝支付订单:cite[7]:cite[8]"""
        out_trade_no = f"VIP{vip_subscription.id}{int(datetime.now().timestamp())}"
        subject = f"购买VIP套餐: {vip_subscription.plan.name}"
        total_amount = float(vip_subscription.payment_amount)

        # 根据不同支付方式调用不同API
        order_string = self.alipay.api_alipay_trade_page_pay(
            out_trade_no=out_trade_no,
            total_amount=total_amount,
            subject=subject,
            return_url=return_url or self.alipay.app_notify_url,
            notify_url=self.alipay.app_notify_url
        )

        # 生成支付链接
        pay_url = f"{self.alipay._gateway}?{order_string}"

        return {
            'out_trade_no': out_trade_no,
            'pay_url': pay_url,
            'order_string': order_string  # 用于APP支付
        }

    def handle_notify(self, data):
        """处理支付宝异步通知:cite[2]:cite[7]"""
        try:
            # 验证签名
            signature = data.pop("sign", None)
            if not signature:
                return False

            success = self.alipay.verify(data, signature)
            if success and data.get("trade_status") in ["TRADE_SUCCESS", "TRADE_FINISHED"]:
                return self._update_payment_status(data)
            return False
        except Exception as e:
            logging.error(f"处理支付宝支付通知异常: {str(e)}")
            return False

    def _update_payment_status(self, notify_data):
        """更新支付状态"""
        out_trade_no = notify_data['out_trade_no']
        trade_no = notify_data['trade_no']  # 支付宝交易号

        subscription = VIPSubscription.query.filter_by(transaction_id=out_trade_no).first()
        if subscription and subscription.status == 'active':
            return True  # 已处理过

        subscription.transaction_id = trade_no
        subscription.status = 'active'
        subscription.starts_at = datetime.now()
        subscription.expires_at = datetime.now() + timedelta(days=subscription.plan.duration_days)

        db.session.commit()
        return True
