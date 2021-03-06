# Copyright 2016 Capital One Services, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from .common import BaseTest
from c7n.executor import MainThreadExecutor
from c7n.resources.elb import ELB
from c7n.filters import FilterValidationError
from nose.tools import raises


class ELBTagTest(BaseTest):

    def test_elb_tag_and_remove(self):
        self.patch(ELB, 'executor_factory', MainThreadExecutor)
        session_factory = self.replay_flight_data('test_elb_tag_and_remove')
        client = session_factory().client('elb')

        policy = self.load_policy({
            'name': 'elb-tag',
            'resource': 'elb',
            'filters': [
                {'LoadBalancerName': 'CloudCustodian'}],
            'actions': [
                {'type': 'tag', 'key': 'xyz', 'value': 'abdef'}]
            },
            session_factory=session_factory)

        resources = policy.run()
        self.assertEqual(len(resources), 1)
        tags = client.describe_tags(
            LoadBalancerNames=['CloudCustodian'])['TagDescriptions'][0]['Tags']
        tag_map = {t['Key']: t['Value'] for t in tags}
        self.assertTrue('xyz' in tag_map)

        policy = self.load_policy({
            'name': 'elb-tag',
            'resource': 'elb',
            'filters': [
                {'LoadBalancerName': 'CloudCustodian'}],
            'actions': [
                {'type': 'remove-tag', 'tags': ['xyz']}]
            },
            session_factory=session_factory)
        resources = policy.run()
        self.assertEqual(len(resources), 1)
        tags = client.describe_tags(
            LoadBalancerNames=['CloudCustodian'])['TagDescriptions'][0]['Tags']
        tag_map = {t['Key']: t['Value'] for t in tags}
        self.assertFalse('xyz' in tag_map)

    def test_elb_tags(self):
        self.patch(ELB, 'executor_factory', MainThreadExecutor)
        session_factory = self.replay_flight_data(
            'test_elb_tags')
        policy = self.load_policy({
            'name': 'elb-mark',
            'resource': 'elb',
            'filters': [{"tag:Platform": "ubuntu"}]},
            session_factory=session_factory)
        resources = policy.run()
        self.assertEqual(len(resources), 1)

    def test_mark_and_match(self):
        session_factory = self.replay_flight_data(
            'test_elb_mark_and_match')
        policy = self.load_policy({
            'name': 'elb-mark',
            'resource': 'elb',
            'filters': [{"LoadBalancerName": 'CloudCustodian'}],
            'actions': [{
                'type': 'mark-for-op', 'op': 'delete',
                'tag': 'custodian_next', 'days': 1}]},
            session_factory=session_factory)
        resources = policy.run()

        self.assertEqual(len(resources), 1)
        tags = session_factory().client('elb').describe_tags(
            LoadBalancerNames=['CloudCustodian'])['TagDescriptions'][0]['Tags']
        tag_map = {t['Key']: t['Value'] for t in tags}
        self.assertTrue('custodian_next' in tag_map)

        policy = self.load_policy({
            'name': 'elb-mark-filter',
            'resource': 'elb',
            'filters': [
                {'type': 'marked-for-op', 'tag': 'custodian_next',
                 'op': 'delete'}]},
            session_factory=session_factory)
        resources = policy.run()
        self.assertEqual(len(resources), 1)


class ELBInstance(BaseTest):

    def test_instance_filter(self):
        session_factory = self.replay_flight_data(
            'test_elb_instance_filter')
        policy = self.load_policy({
            'name': 'elb-instance',
            'resource': 'elb',
            'filters': [
                {'type': 'instance',
                 'key': 'ImageId',
                 'value': 'ami-40d28157'}],
            }, session_factory=session_factory)
        resources = policy.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['LoadBalancerName'], 'balanced')


class HealthCheckProtocolMismatchTest(BaseTest):

    def test_healthcheck_protocol_mismatch(self):
        session_factory = self.replay_flight_data(
            'test_healthcheck_protocol_mismatch')
        policy = self.load_policy({
            'name': 'healthcheck-protocol-mismatch',
            'resource': 'elb',
            'filters': [
                {'type': 'healthcheck-protocol-mismatch'}
            ]},
            session_factory=session_factory)

        resources = policy.run()
        self.assertEqual(len(resources), 3)

        # make sure we matched the right load balcners
        elb_names = set([elb['LoadBalancerName'] for elb in resources])
        self.assertEqual(
            elb_names, set(
                ['test-elb-no-listeners',
                 'test-elb-protocol-matches',
                 'test-elb-multiple-listeners']))


class SSLPolicyTest(BaseTest):

    def test_ssl_ciphers(self):
        session_factory = self.replay_flight_data(
            'test_ssl_ciphers')
        policy = self.load_policy({
            'name': 'test-ssl-ciphers',
            'resource': 'elb',
            'filters': [
                {'type': 'ssl-policy',
                 'blacklist': ['Protocol-SSLv2']}
            ]},
            session_factory=session_factory)
        resources = policy.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['LoadBalancerName'],
            'test-elb-invalid-policy')

    @raises(FilterValidationError)
    def test_filter_validation_no_blacklist(self):
        self.load_policy({
            'name': 'test-ssl-ciphers',
            'resource': 'elb',
            'filters': [
                {'type': 'ssl-policy'}
            ]},
            session_factory=None, validate=False)
        self.fail("validtion error should have been thrown")

    @raises(FilterValidationError)
    def test_filter_validation_blacklist_not_iterable(self):
        self.load_policy({
            'name': 'test-ssl-ciphers',
            'resource': 'elb',
            'filters': [
                {'type': 'ssl-policy', 'blacklist': 'single-value'}
            ]},
            session_factory=None, validate=False)
        self.fail("validtion error should have been thrown")


class TestDefaultVpc(BaseTest):

    def test_elb_default_vpc(self):
        session_factory = self.replay_flight_data('test_elb_default_vpc')
        p = self.load_policy(
            {'name': 'elb-default-filters',
             'resource': 'elb',
             'filters': [
                 {'type': 'default-vpc'}]},
            config={'region': 'us-west-2'},
            session_factory=session_factory)

        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['LoadBalancerName'], 'test-load-balancer')


class TestModifyVpcSecurityGroupsAction(BaseTest):

    def test_elb_remove_security_groups(self):
        # Test conditions:
        #   - running ELB in default VPC
        #   - security group named TEST-PROD-ONLY-SG exists in VPC and is attached to test ELB
        session_factory = self.replay_flight_data('test_elb_remove_security_groups')
        client = session_factory().client('ec2')
        default_sg_id = client.describe_security_groups(
            GroupNames=[
                'default',
            ]
        )['SecurityGroups'][0]['GroupId']
        p = self.load_policy(
            {'name': 'elb-modify-security-groups-filter',
             'resource': 'elb',
             'filters': [
                 {'type': 'security-group', 'key': 'GroupName', 'value': '(.*PROD-ONLY.*)', 'op': 'regex'}],
             'actions': [
                 {'type': 'modify-security-groups', 'remove': 'matched', 'isolation-group': default_sg_id}]
             },
        session_factory=session_factory)

        resources = p.run()
        clean_resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['LoadBalancerName'], 'test-load-balancer')
        self.assertEqual(len(clean_resources), 0)

    def test_elb_add_security_group(self):
        # Test conditions:
        #   - running one ELB with 'default' VPC security group attached
        #   - security group named TEST-PROD-ONLY-SG exists in VPC and is not attached to ELB
        session_factory = self.replay_flight_data('test_elb_add_security_group')

        policy = self.load_policy({
            'name': 'add-sg-to-prod-elb',
            'resource': 'elb',
            'filters': [
                {'type': 'security-group', 'key': 'GroupName', 'value': 'default'},
                {'type': 'value', 'key': 'LoadBalancerName', 'value': 'test-load-balancer'}],
            'actions': [
                {'type': 'modify-security-groups', 'add': 'sg-411b413c'}
            ]
        },
        session_factory=session_factory)

        resources = policy.run()
        self.assertEqual(len(resources[0]['SecurityGroups']), 1)
        after_resources = policy.run()
        self.assertEqual(len(after_resources[0]['SecurityGroups']), 2)

    def test_elb_add_security_groups(self):
        # Test conditions:
        #   - running one ELB with 'default' VPC security group attached
        #   - security groups named TEST-PROD-ONLY-SG, TEST-SG1, and TEST-SG2 exist in VPC - not attached to ELB

        session_factory = self.replay_flight_data('test_elb_add_security_groups')
        policy = self.load_policy({
            'name': 'add-sgs-to-prod-elb',
            'resource': 'elb',
            'filters': [
                {'type': 'security-group', 'key': 'GroupName', 'value': 'default'},
                {'type': 'value', 'key': 'LoadBalancerName', 'value': 'test-load-balancer'}],
            'actions': [
                {'type': 'modify-security-groups', 'add': ['sg-411b413c', 'sg-8a4b64f7', 'sg-5d4a6520']}
            ]
        },
        session_factory=session_factory)

        resources = policy.run()
        self.assertEqual(len(resources[0]['SecurityGroups']), 1)
        after_resources = policy.run()
        self.assertEqual(len(after_resources[0]['SecurityGroups']), 4)


    def test_elb_remove_all_security_groups(self):
        # Test conditions:
        #   - running one ELB with 'default' and 'TEST-PROD-ONLY-SG' VPC security groups attached
        session_factory = self.replay_flight_data('test_elb_remove_all_security_groups')
        client = session_factory().client('ec2')

        default_sg_id = client.describe_security_groups(
            GroupNames=[
                'default',
            ]
        )['SecurityGroups'][0]['GroupId']

        policy = self.load_policy({
            'name': 'add-sg-to-prod-elb',
            'resource': 'elb',
            'filters': [
                {'type': 'value', 'key': 'LoadBalancerName', 'value': 'test-load-balancer'}],
            'actions': [
                {'type': 'modify-security-groups', 'remove': 'all', 'isolation-group': default_sg_id},
            ]
        },
        session_factory=session_factory)

        resources = policy.run()
        self.assertEqual(len(resources[0]['SecurityGroups']), 2)
        after_resources = policy.run()
        self.assertEqual(len(after_resources[0]['SecurityGroups']), 1)
        # Check that it is indeed the isolation group on the ELB
        self.assertEqual(after_resources[0]['SecurityGroups'][0], default_sg_id)
