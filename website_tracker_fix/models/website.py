from urllib.parse import urlsplit

from odoo import models
from odoo.http import request


class Website(models.Model):
    _inherit = 'website'

    def _control_third_party_trackers_in_html(self, html_content):
        """Process custom HTML to block third-party tracker scripts/iframes.

        Mirrors the blocking logic in ir_qweb._post_processing_att but operates
        on a raw HTML string (used for custom_code_head / custom_code_footer).
        """
        self.ensure_one()
        if not html_content:
            return html_content

        # Only block when cookies bar + blocking are both enabled and cookies
        # haven't been accepted by this visitor yet.
        if not (self.cookies_bar and self.block_third_party_domains):
            return html_content

        if self.env.context.get('cookies_allowed'):
            return html_content

        if request and request.env.user.has_group('website.group_website_restricted_editor'):
            return html_content

        try:
            from lxml import etree
        except ImportError:
            return html_content

        blocked_domains = self._get_blocked_third_party_domains_list()

        try:
            root = etree.fromstring(f'<div>{html_content}</div>', etree.HTMLParser())
        except Exception:
            return html_content

        body = root.find('.//body')
        wrapper = body.find('div') if body is not None else root.find('div')
        target = wrapper if wrapper is not None else root

        for tag in ('script', 'iframe'):
            for element in target.iter(tag):
                src = element.get('src') or ''
                if not src:
                    continue
                src_host = urlsplit(src.lower()).hostname
                if not src_host:
                    continue
                should_block = any(
                    src_host == domain.removeprefix('www.')
                    or src_host.endswith('.' + domain.removeprefix('www.'))
                    for domain in blocked_domains
                    if domain
                )
                if should_block:
                    element.set('data-nocookie-src', src)
                    element.set('data-need-cookies-approval', 'true')
                    element.set('src', 'about:blank')

        return ''.join(
            etree.tostring(child, encoding='unicode', method='html')
            for child in target
        )
