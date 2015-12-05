# Copyright (c) 2014 Intel Corporation

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# pylint: disable=missing-docstring

""" Tests for the backend package """

from __future__ import print_function, absolute_import
import os

try:
    from lxml import etree
except ImportError:
    import xml.etree.cElementTree as etree
import mock
import nose.tools as nt
from nose.plugins.skip import SkipTest

from framework import results, backends, grouptools, status
import framework.tests.utils as utils
from .backends_tests import BACKEND_INITIAL_META


JUNIT_SCHEMA = 'framework/tests/schema/junit-7.xsd'

doc_formatter = utils.DocFormatter({'separator': grouptools.SEPARATOR})

_XML = """\
<?xml version='1.0' encoding='utf-8'?>
  <testsuites>
    <testsuite name="piglit" tests="5">
      <testcase classname="piglit.foo.bar" name="a-test" status="pass" time="1.12345">
        <system-out>this/is/a/command\nThis is stdout</system-out>
        <system-err>this is stderr

time start: 1.0
time end: 4.5
        </system-err>
      </testcase>
      <testsuite name="piglit.bar" time="1.234" tests="4" failures="1" skipped="1" errors="1">
        <system-err>this is stderr

time start: 1.0
time end: 4.5
</system-err>
        <system-out>this/is/a/command\nThis is stdout</system-out>
        <testcase name="subtest1" status="pass"/>
        <testcase name="subtest2" status="fail">
          <failed/>
        </testcase>
        <testcase name="subtest3" status="crash">
          <error/>
        </testcase>
        <testcase name="subtest4" status="skip">
          <skipped/>
        </testcase>
      </testsuite>
    </testsuite>
  </testsuites>
"""


def setup_module():
    utils.set_compression('none')


def teardown_module():
    utils.unset_compression()


class TestJunitNoTests(utils.StaticDirectory):
    @classmethod
    def setup_class(cls):
        super(TestJunitNoTests, cls).setup_class()
        test = backends.junit.JUnitBackend(cls.tdir)
        test.initialize(BACKEND_INITIAL_META)
        test.finalize()
        cls.test_file = os.path.join(cls.tdir, 'results.xml')

    @utils.no_error
    def test_xml_well_formed(self):
        """backends.junit.JUnitBackend: initialize and finalize produce well formed xml

        While it will produce valid XML, it cannot produc valid JUnit, since
        JUnit requires at least one test to be valid

        """
        etree.parse(self.test_file)


class TestJUnitSingleTest(TestJunitNoTests):
    @classmethod
    def setup_class(cls):
        super(TestJUnitSingleTest, cls).setup_class()
        cls.test_file = os.path.join(cls.tdir, 'results.xml')

        result = results.TestResult()
        result.time.end = 1.2345
        result.result = 'pass'
        result.out = 'this is stdout'
        result.err = 'this is stderr'
        result.command = 'foo'

        test = backends.junit.JUnitBackend(cls.tdir)
        test.initialize(BACKEND_INITIAL_META)
        with test.write_test(grouptools.join('a', 'test', 'group', 'test1')) as t:
            t(result)
        test.finalize()

    def test_xml_well_formed(self):
        """backends.junit.JUnitBackend.write_test(): (once) produces well formed xml"""
        super(TestJUnitSingleTest, self).test_xml_well_formed()

    def test_xml_valid(self):
        """backends.junit.JUnitBackend.write_test(): (once) produces valid xml"""
        if etree.__name__ != 'lxml.etree':
            raise SkipTest('Test requires lxml features')
        schema = etree.XMLSchema(file=JUNIT_SCHEMA)
        with open(self.test_file, 'r') as f:
            nt.ok_(schema.validate(etree.parse(f)), msg='xml is not valid')


class TestJUnitMultiTest(TestJUnitSingleTest):
    @classmethod
    def setup_class(cls):
        super(TestJUnitMultiTest, cls).setup_class()

        result = results.TestResult()
        result.time.end = 1.2345
        result.result = 'pass'
        result.out = 'this is stdout'
        result.err = 'this is stderr'
        result.command = 'foo'

        cls.test_file = os.path.join(cls.tdir, 'results.xml')
        test = backends.junit.JUnitBackend(cls.tdir)
        test.initialize(BACKEND_INITIAL_META)
        with test.write_test(grouptools.join('a', 'test', 'group', 'test1')) as t:
            t(result)

        result.result = 'fail'
        with test.write_test(
                grouptools.join('a', 'different', 'test', 'group', 'test2')) as t:
            t(result)
        test.finalize()

    def test_xml_well_formed(self):
        """backends.junit.JUnitBackend.write_test(): (twice) produces well formed xml"""
        super(TestJUnitMultiTest, self).test_xml_well_formed()

    def test_xml_valid(self):
        """backends.junit.JUnitBackend.write_test(): (twice) produces valid xml"""
        super(TestJUnitMultiTest, self).test_xml_valid()


@doc_formatter
def test_junit_replace():
    """backends.junit.JUnitBackend.write_test(): '{separator}' is replaced with '.'"""
    with utils.tempdir() as tdir:
        result = results.TestResult()
        result.time.end = 1.2345
        result.result = 'pass'
        result.out = 'this is stdout'
        result.err = 'this is stderr'
        result.command = 'foo'

        test = backends.junit.JUnitBackend(tdir)
        test.initialize(BACKEND_INITIAL_META)
        with test.write_test(grouptools.join('a', 'test', 'group', 'test1')) as t:
            t(result)
        test.finalize()

        test_value = etree.parse(os.path.join(tdir, 'results.xml')).getroot()

    nt.assert_equal(test_value.find('.//testcase').attrib['classname'],
                    'piglit.a.test.group')


@utils.not_raises(etree.ParseError)
def test_junit_skips_bad_tests():
    """backends.junit.JUnitBackend: skips illformed tests"""
    with utils.tempdir() as tdir:
        result = results.TestResult()
        result.time.end = 1.2345
        result.result = 'pass'
        result.out = 'this is stdout'
        result.err = 'this is stderr'
        result.command = 'foo'

        test = backends.junit.JUnitBackend(tdir)
        test.initialize(BACKEND_INITIAL_META)
        with test.write_test(grouptools.join('a', 'test', 'group', 'test1')) as t:
            t(result)
        with open(os.path.join(tdir, 'tests', '1.xml'), 'w') as f:
            f.write('bad data')

        test.finalize()


class TestJUnitLoad(utils.StaticDirectory):
    """Methods that test loading JUnit results."""
    __instance = None

    @classmethod
    def setup_class(cls):
        super(TestJUnitLoad, cls).setup_class()
        cls.xml_file = os.path.join(cls.tdir, 'results.xml')

        with open(cls.xml_file, 'w') as f:
            f.write(_XML)

        cls.testname = grouptools.join('foo', 'bar', 'a-test')
        cls.subtestname = 'bar'

    @classmethod
    def xml(cls):
        if cls.__instance is None:
            cls.__instance = backends.junit._load(cls.xml_file)
        return cls.__instance

    @utils.no_error
    def test_no_errors(self):
        """backends.junit._load: Raises no errors for valid junit."""
        self.xml()

    def test_return_testrunresult(self):
        """backends.junit._load: returns a TestrunResult instance"""
        nt.assert_is_instance(self.xml(), results.TestrunResult)

    @doc_formatter
    def test_replace_sep(self):
        """backends.junit._load: replaces '.' with '{separator}'"""
        nt.assert_in(self.testname, self.xml().tests)

    def test_testresult_instance(self):
        """backends.junit._load: replaces result with TestResult instance."""
        nt.assert_is_instance(self.xml().tests[self.testname], results.TestResult)

    def test_status_instance(self):
        """backends.junit._load: a status is found and loaded."""
        nt.assert_is_instance(self.xml().tests[self.testname].result,
                              status.Status)

    def test_time_start(self):
        """backends.junit._load: Time.start is loaded correctly."""
        time = self.xml().tests[self.testname].time
        nt.assert_is_instance(time, results.TimeAttribute)
        nt.eq_(time.start, 1.0)

    def test_time_end(self):
        """backends.junit._load: Time.end is loaded correctly."""
        time = self.xml().tests[self.testname].time
        nt.assert_is_instance(time, results.TimeAttribute)
        nt.eq_(time.end, 4.5)

    def test_command(self):
        """backends.junit._load: command is loaded correctly."""
        test = self.xml().tests[self.testname].command
        nt.assert_equal(test, 'this/is/a/command')

    def test_out(self):
        """backends.junit._load: stdout is loaded correctly."""
        test = self.xml().tests[self.testname].out
        nt.assert_equal(test, 'This is stdout')

    def test_err(self):
        """backends.junit._load: stderr is loaded correctly."""
        test = self.xml().tests[self.testname].err
        nt.eq_(
            test, 'this is stderr\n\ntime start: 1.0\ntime end: 4.5\n        ')

    def test_totals(self):
        """backends.junit._load: Totals are calculated."""
        nt.ok_(bool(self.xml()))

    @utils.no_error
    def test_load_file(self):
        """backends.junit.load: Loads a file directly"""
        backends.junit.REGISTRY.load(self.xml_file, 'none')

    @utils.no_error
    def test_load_dir(self):
        """backends.junit.load: Loads a directory"""
        backends.junit.REGISTRY.load(self.tdir, 'none')

    def test_subtest_added(self):
        """backends.junit._load: turns secondlevel <testsuite> into test with stubtests"""
        xml = self.xml()
        nt.assert_in(self.subtestname, xml.tests)

    def test_subtest_time(self):
        """backends.junit._load: handles time from subtest"""
        time = self.xml().tests[self.subtestname].time
        nt.assert_is_instance(time, results.TimeAttribute)
        nt.eq_(time.start, 1.0)
        nt.eq_(time.end, 4.5)

    def test_subtest_out(self):
        """backends.junit._load: subtest stderr is loaded correctly"""
        test = self.xml().tests[self.subtestname].out
        nt.eq_(test, 'This is stdout')

    def test_subtest_err(self):
        """backends.junit._load: stderr is loaded correctly."""
        test = self.xml().tests[self.subtestname].err
        nt.eq_(test, 'this is stderr\n\ntime start: 1.0\ntime end: 4.5\n')

    def test_subtest_statuses(self):
        """backends.juint._load: subtest statuses are restored correctly

        This is not implemented as separate tests or a generator becuase while
        it asserts multiple values, it is testing one peice of funcitonality:
        whether the subtests are restored correctly.

        """
        test = self.xml().tests[self.subtestname]

        subtests = [
            ('subtest1', 'pass'),
            ('subtest2', 'fail'),
            ('subtest3', 'crash'),
            ('subtest4', 'skip'),
        ]

        for name, value in subtests:
            nt.eq_(test.subtests[name], value)


def test_load_file_name():
    """backends.junit._load: uses the filename for name if filename != 'results'
    """
    with utils.tempdir() as tdir:
        filename = os.path.join(tdir, 'foobar.xml')
        with open(filename, 'w') as f:
            f.write(_XML)

        test = backends.junit.REGISTRY.load(filename, 'none')
    nt.assert_equal(test.name, 'foobar')


def test_load_folder_name():
    """backends.junit._load: uses the folder name if the result is 'results'"""
    with utils.tempdir() as tdir:
        os.mkdir(os.path.join(tdir, 'a cool test'))
        filename = os.path.join(tdir, 'a cool test', 'results.xml')
        with open(filename, 'w') as f:
            f.write(_XML)

        test = backends.junit.REGISTRY.load(filename, 'none')
    nt.assert_equal(test.name, 'a cool test')


@utils.test_in_tempdir
def test_load_default_name():
    """backends.junit._load: uses 'junit result' for name as fallback"""
    with utils.tempdir() as tdir:
        os.chdir(tdir)

        filename = 'results.xml'
        with open(filename, 'w') as f:
            f.write(_XML)

        test = backends.junit.REGISTRY.load(filename, 'none')

    nt.assert_equal(test.name, 'junit result')


class TestJunitSubtestWriting(object):
    """Tests for Junit subtest writing.

    Junit needs to write out subtests as full tests, so jenkins will consume
    them correctly.

    """
    __patchers = [
        mock.patch('framework.backends.abstract.shutil.move', mock.Mock()),
    ]

    @staticmethod
    def _make_result():
        result = results.TestResult()
        result.time.end = 1.2345
        result.result = 'pass'
        result.out = 'this is stdout'
        result.err = 'this is stderr'
        result.command = 'foo'
        result.subtests['foo'] = 'skip'
        result.subtests['bar'] = 'fail'
        result.subtests['oink'] = 'crash'

        test = backends.junit.JUnitBackend('foo')
        mock_open = mock.mock_open()
        with mock.patch('framework.backends.abstract.open', mock_open):
            with test.write_test(grouptools.join('a', 'group', 'test1')) as t:
                t(result)

        # Return an xml object
        # This seems pretty fragile, but I don't see a better way to get waht
        # we want
        return etree.fromstring(mock_open.mock_calls[-3][1][0])

    @classmethod
    def setup_class(cls):
        for p in cls.__patchers:
            p.start()

        cls.output = cls._make_result()

    @classmethod
    def teardown_class(cls):
        for p in cls.__patchers:
            p.stop()

    def test_suite(self):
        """backends.junit.JUnitBackend.write_test: wraps the cases in a suite"""
        nt.eq_(self.output.tag, 'testsuite')

    def test_cases(self):
        """backends.junit.JUnitBackend.write_test: has one <testcase> per subtest"""
        nt.eq_(len(self.output.findall('testcase')), 3)

    @utils.nose_generator
    def test_metadata(self):
        """backends.junit.JUnitBackend.write_test: metadata written into the
        suite

        """
        def test(actual, expected):
            nt.eq_(expected, actual)

        descrption = ('backends.junit.JUnitBackend.write_test: '
                      '{} is written into the suite')

        if self.output.tag != 'testsuite':
            raise Exception('Could not find a testsuite!')

        tests = [
            (self.output.find('system-out').text, 'this is stdout',
             'system-out'),
            (self.output.find('system-err').text,
             'this is stderr\n\nstart time: 0.0\nend time: 1.2345\n',
             'system-err'),
            (self.output.attrib.get('name'), 'piglit.a.group.test1', 'name'),
            (self.output.attrib.get('time'), '1.2345', 'timestamp'),
            (self.output.attrib.get('failures'), '1', 'failures'),
            (self.output.attrib.get('skipped'), '1', 'skipped'),
            (self.output.attrib.get('errors'), '1', 'errors'),
            (self.output.attrib.get('tests'), '3', 'tests'),
        ]

        for actual, expected, name in tests:
            test.description = descrption.format(name)
            yield test, actual, expected

    def test_testname(self):
        """backends.junit.JUnitBackend.write_test: the testname should be the subtest name"""
        nt.ok_(self.output.find('testcase[@name="foo"]') is not None)

    def test_fail(self):
        """Backends.junit.JUnitBackend.write_test: add <failure> if the subtest failed"""
        nt.eq_(len(self.output.find('testcase[@name="bar"]').findall('failure')), 1)

    def test_skip(self):
        """Backends.junit.JUnitBackend.write_test: add <skipped> if the subtest skipped"""
        nt.eq_(len(self.output.find('testcase[@name="foo"]').findall('skipped')), 1)

    def test_error(self):
        """Backends.junit.JUnitBackend.write_test: add <error> if the subtest crashed"""
        nt.eq_(len(self.output.find('testcase[@name="oink"]').findall('error')), 1)


class TestJunitSubtestFinalize(utils.StaticDirectory):
    @classmethod
    def setup_class(cls):
        super(TestJunitSubtestFinalize, cls).setup_class()

        result = results.TestResult()
        result.time.end = 1.2345
        result.result = 'pass'
        result.out = 'this is stdout'
        result.err = 'this is stderr'
        result.command = 'foo'
        result.subtests['foo'] = 'pass'
        result.subtests['bar'] = 'fail'

        test = backends.junit.JUnitBackend(cls.tdir)
        test.initialize(BACKEND_INITIAL_META)
        with test.write_test(grouptools.join('a', 'test', 'group', 'test1')) as t:
            t(result)
        test.finalize()

    @utils.not_raises(etree.ParseError)
    def test_valid_xml(self):
        """backends.jUnit.JunitBackend.finalize: produces valid xml with subtests"""
        etree.parse(os.path.join(self.tdir, 'results.xml'))

    def test_valid_junit(self):
        """backends.jUnit.JunitBackend.finalize: prodives valid junit with subtests"""
        if etree.__name__ != 'lxml.etree':
            raise SkipTest('Test requires lxml features')

        schema = etree.XMLSchema(file=JUNIT_SCHEMA)
        xml = etree.parse(os.path.join(self.tdir, 'results.xml'))
        nt.ok_(schema.validate(xml), msg='xml is not valid')
