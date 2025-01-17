#!/usr/bin/python
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json

from charms.reactive import (
    Endpoint,
    set_flag,
    clear_flag
)

from charms.reactive import (
    when,
    when_any,
    when_not
)

from charmhelpers.core import (
    hookenv,
    unitdata
)


DB = unitdata.kv()


class KubeControlProvider(Endpoint):
    """
    Implements the kubernetes-master side of the kube-control interface.
    """
    @when_any('endpoint.{endpoint_name}.joined',
              'endpoint.{endpoint_name}.changed')
    def joined_or_changed(self):
        set_flag(self.expand_name('{endpoint_name}.connected'))

        hookenv.log('Checking for gpu-enabled workers')
        if self._get_gpu():
            set_flag(
                self.expand_name(
                    '{endpoint_name}.gpu.available'))
        else:
            clear_flag(
                self.expand_name(
                    '{endpoint_name}.gpu.available'))

        clear_flag(self.expand_name('endpoint.{endpoint_name}.changed'))

    @when_not('endpoint.{endpoint_name}.joined')
    def departed(self):
        """
        Remove all states.
        """
        clear_flag(
            self.expand_name(
                '{endpoint_name}.connected'))
        clear_flag(
            self.expand_name(
                '{endpoint_name}.gpu.available'))

    def set_dns(self, port, domain, sdn_ip, enable_kube_dns):
        """
        Send DNS info to the remote units.

        We'll need the port, domain, and sdn_ip of the dns service. If
        sdn_ip is not required in your deployment, the units private-ip
        is available implicitly.
        """
        for relation in self.relations:
            relation.to_publish_raw.update({
                'port': port,
                'domain': domain,
                'sdn-ip': sdn_ip,
                'enable-kube-dns': enable_kube_dns,
            })

    def auth_user(self):
        """
        Return the kubelet_user value on the wire from the requestors.
        """
        requests = []

        for unit in self.all_joined_units:
            requests.append(
                (unit.unit_name,
                {'user': unit.received_raw.get('kubelet_user'),
                 'group': unit.received_raw.get('auth_group')})
            )

        return requests

    def sign_auth_request(self, scope, user, kubelet_token, proxy_token,
                          client_token):
        """
        Send authorization tokens to the requesting unit.
        """
        cred = {
            'scope': scope,
            'kubelet_token': kubelet_token,
            'proxy_token': proxy_token,
            'client_token': client_token
        }

        if not DB.get('creds'):
            DB.set('creds', {})

        all_creds = DB.get('creds')
        all_creds[user] = cred
        DB.set('creds', all_creds)

        for relation in self.relations:
            relation.to_publish.update({
                'creds': all_creds
            })

    def _get_gpu(self):
        """
        Return True if any remote worker is gpu-enabled.
        """
        for unit in self.all_joined_units:
            if unit.received_raw.get('gpu') == 'True':
                hookenv.log('Unit {} has gpu enabled'.format(unit))
                return True

        return False

    def set_cluster_tag(self, cluster_tag):
        """
        Send the cluster tag to the remote units.
        """
        for relation in self.relations:
            relation.to_publish_raw.update({
                'cluster-tag': cluster_tag
            })

    def set_registry_location(self, registry_location):
        """
        Send the registry location to the remote units.
        """
        for relation in self.relations:
            relation.to_publish_raw.update({
                'registry-location': registry_location
            })
