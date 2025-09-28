# services/pay/WeChat.py
import logging
from datetime import datetime, timedelta

from flask import json
from jd_wechatpay import WeChatPay, WeChatPayType  # 或使用 wechatpy

from src.models import db, VIPSubscription


class WeChatPayService:
    def __init__(self, app=None):
        self.wxpay = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """初始化微信支付实例:cite[1]"""
        try:
            self.wxpay = WeChatPay(
                WeChatPayType.APP,  # 根据前端类型调整: APP, JSAPI, NATIVE等
                mch_id=app.config['WECHAT_MCHID'],
                private_key=app.config['WECHAT_PRIVATE_KEY'],
                cert_serial_no=app.config['WECHAT_CERT_SERIAL_NO'],
                app_id=app.config['WECHAT_APPID'],
                api_v3_key=app.config['WECHAT_API_V3_KEY'],
                notify_url=app.config['WECHAT_NOTIFY_URL'],
                cert_dir=app.config['WECHAT_CERT_DIR'],
                logger=logging.getLogger('wechatpay'),
                partner_mode=False  # 直连模式，服务商模式设为True
            )
        except Exception as e:
            logging.error(f"初始化微信支付失败: {str(e)}")
            raise

    def create_payment(self, vip_subscription, user_openid=None):
        """创建微信支付预订单:cite[5]:cite[6]"""
        out_trade_no = f"VIP{vip_subscription.id}{int(datetime.now().timestamp())}"  # 商户订单号
        description = f"购买VIP套餐: {vip_subscription.plan.name}"
        amount = int(float(vip_subscription.payment_amount) * 100)  # 金额(分)

        # 调用统一下单API
        code, message = self.wxpay.pay.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={'total': amount},
            payer={'openid': user_openid} if user_openid else None,  # JSAPI支付需传openid
            pay_type=WeChatPayType.APP  # 根据前端调整
        )

        if code == 200:
            # 返回前端所需的支付参数
            prepay_data = json.loads(message)
            return {
                'prepay_id': prepay_data.get('prepay_id'),
                'out_trade_no': out_trade_no,
                'payment_params': self._get_payment_params(prepay_data)  # 生成前端支付参数
            }
        else:
            raise Exception(f"微信预支付失败: {message}")

    def _get_payment_params(self, prepay_data):
        """生成前端支付参数(APP/JSAPI):cite[6]"""
        timestamp = str(int(datetime.now().timestamp()))
        nonce_str = self.wxpay.generate_nonce_str()
        package = f"prepay_id={prepay_data['prepay_id']}"

        # 生成签名
        sign_data = {
            'appId': self.wxpay.app_id,
            'timeStamp': timestamp,
            'nonceStr': nonce_str,
            'package': package,
            'signType': 'RSA' if self.wxpay._sign_method == 'RSA' else 'HMAC-SHA256'
        }
        sign = self.wxpay.sign(sign_data)

        return {
            'appId': self.wxpay.app_id,
            'timeStamp': timestamp,
            'nonceStr': nonce_str,
            'package': package,
            'signType': sign_data['signType'],
            'paySign': sign,
            'out_trade_no': prepay_data.get('out_trade_no')
        }

    def handle_notify(self, data):
        """处理微信支付异步通知:cite[9]"""
        try:
            # 解析并验证通知数据
            result = self.wxpay.callback(data)
            if result and result.get('event_type') == 'TRANSACTION.SUCCESS':
                resource = result['resource']
                # 解密资源数据
                decrypt_data = self.wxpay.decrypt(
                    resource['ciphertext'],
                    resource['associated_data'],
                    resource['nonce']
                )
                notify_data = json.loads(decrypt_data)

                # 验证订单状态
                if notify_data['trade_state'] == 'SUCCESS':
                    return self._update_payment_status(notify_data)
            return False
        except Exception as e:
            logging.error(f"处理微信支付通知异常: {str(e)}")
            return False

    def _update_payment_status(self, notify_data):
        """更新支付状态"""
        out_trade_no = notify_data['out_trade_no']
        transaction_id = notify_data['transaction_id']

        # 根据out_trade_no找到对应订阅记录
        subscription = VIPSubscription.query.filter_by(transaction_id=out_trade_no).first()
        if subscription and subscription.status == 'active':
            return True  # 已处理过，防止重复通知

        # 更新订阅记录
        subscription.transaction_id = transaction_id
        subscription.status = 'active'
        subscription.starts_at = datetime.now()
        # 根据套餐时长设置过期时间
        subscription.expires_at = datetime.now() + timedelta(days=subscription.plan.duration_days)

        db.session.commit()
        return True