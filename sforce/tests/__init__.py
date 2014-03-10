from unittest import TestSuite
from unittest import TestLoader

from sforce.tests.test_client import BaseResourceTest
from sforce.tests.test_client import JsonResourceTest
from sforce.tests.test_client import DateRangeResourceTest
from sforce.tests.test_client import InstanceResourceTest
from sforce.tests.test_client import ExternalIdInstanceResourceTest
from sforce.tests.test_client import RestApiTest
from sforce.tests.test_client import ModelSyncTest
from sforce.tests.test_client import SalesForceApiTest


def suite():
    suite = TestSuite()
    loader = TestLoader()

    test_cases = [
        BaseResourceTest,
        JsonResourceTest,
        DateRangeResourceTest,
        InstanceResourceTest,
        ExternalIdInstanceResourceTest,
        RestApiTest,
        ModelSyncTest,
        SalesForceApiTest,
    ]

    for test_case in test_cases:
        tests = loader.loadTestsFromTestCase(test_case)
        suite.addTests(tests)

    return suite
