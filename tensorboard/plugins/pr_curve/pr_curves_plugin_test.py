# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
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
# ==============================================================================
"""Integration tests for the pr_curves plugin."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import os.path

import numpy as np
import six
import tensorflow as tf

from tensorboard.backend.event_processing import plugin_event_multiplexer as event_multiplexer  # pylint: disable=line-too-long
from tensorboard.plugins import base_plugin
from tensorboard.plugins.pr_curve import pr_curve_demo
from tensorboard.plugins.pr_curve import pr_curves_plugin


class PrCurvesPluginTest(tf.test.TestCase):

  def setUp(self):
    super(PrCurvesPluginTest, self).setUp()
    logdir = os.path.join(self.get_temp_dir(), 'logdir')

    # Generate data.
    pr_curve_demo.run_all(
        logdir=logdir,
        steps=3,
        thresholds=5,
        verbose=False)

    # Create a multiplexer for reading the data we just wrote.
    multiplexer = event_multiplexer.EventMultiplexer()
    multiplexer.AddRunsFromDirectory(logdir)
    multiplexer.Reload()

    context = base_plugin.TBContext(logdir=logdir, multiplexer=multiplexer)
    self.plugin = pr_curves_plugin.PrCurvesPlugin(context)

  def validatePrCurveEntry(
      self,
      expected_step,
      expected_precision,
      expected_recall,
      pr_curve_entry):
    """Checks that the values stored within a tensor are correct.

    Args:
      expected_step: The expected step.
      expected_precision: A list of float precision values.
      expected_recall: A list of float recall values.
      pr_curve_entry: The PR curve entry to evaluate.
    """
    self.assertEqual(expected_step, pr_curve_entry['step'])
    # We use an absolute error instead of a relative one because the expected
    # values are small. The default relative error (rtol) of 1e-7 yields many
    # undesired test failures.
    np.testing.assert_allclose(
        expected_precision, pr_curve_entry['precision'], rtol=0, atol=1e-7)
    np.testing.assert_allclose(
        expected_recall, pr_curve_entry['recall'], rtol=0, atol=1e-7)

  def computeCorrectDescription(self, standard_deviation):
    """Generates a correct description.

    Arguments:
      standard_deviation: An integer standard deviation value.

    Returns:
      The correct description given a standard deviation value.
    """
    description = ('<p>The probabilities used to create this PR curve are '
                   'generated from a normal distribution. Its standard '
                   'deviation is initially %d and decreases'
                   ' over time.</p>') % standard_deviation

  def testRoutesProvided(self):
    """Tests that the plugin offers the correct routes."""
    routes = self.plugin.get_plugin_apps()
    self.assertIsInstance(routes['/tags'], collections.Callable)
    self.assertIsInstance(routes['/pr_curves'], collections.Callable)
    self.assertIsInstance(routes['/available_steps'], collections.Callable)

  def testTagsProvided(self):
    """Tests that tags are provided."""
    tags_response = self.plugin.tags_impl()

    # Assert that the runs are right.
    self.assertItemsEqual(
        ['colors', 'mask_every_other_prediction'], list(tags_response.keys()))

    # Assert that the tags for each run are correct.
    self.assertItemsEqual(
        ['red/pr_curves', 'green/pr_curves', 'blue/pr_curves'],
        list(tags_response['colors'].keys()))
    self.assertItemsEqual(
        ['red/pr_curves', 'green/pr_curves', 'blue/pr_curves'],
        list(tags_response['mask_every_other_prediction'].keys()))

    # Verify the data for each run-tag combination.
    self.assertDictEqual({
      'displayName': 'classifying red',
      'description': self.computeCorrectDescription(168),
    }, tags_response['colors']['red/pr_curves'])
    self.assertDictEqual({
      'displayName': 'classifying green',
      'description': self.computeCorrectDescription(210),
    }, tags_response['colors']['green/pr_curves'])
    self.assertDictEqual({
      'displayName': 'classifying blue',
      'description': self.computeCorrectDescription(252),
    }, tags_response['colors']['blue/pr_curves'])
    self.assertDictEqual({
      'displayName': 'classifying red',
      'description': self.computeCorrectDescription(168),
    }, tags_response['mask_every_other_prediction']['red/pr_curves'])
    self.assertDictEqual({
      'displayName': 'classifying green',
      'description': self.computeCorrectDescription(210),
    }, tags_response['mask_every_other_prediction']['green/pr_curves'])
    self.assertDictEqual({
      'displayName': 'classifying blue',
      'description': self.computeCorrectDescription(252),
    }, tags_response['mask_every_other_prediction']['blue/pr_curves'])

  def testAvailableSteps(self):
    """Tests that runs are mapped to correct available steps."""
    self.assertDictEqual({
        'colors': [0, 1, 2],
        'mask_every_other_prediction': [0, 1, 2],
    }, self.plugin.available_steps_impl())

  def testPrCurvesDataCorrect(self):
    """Tests that responses for PR curves for run-tag combos are correct."""
    pr_curves_response = self.plugin.pr_curves_impl(
        ['colors', 'mask_every_other_prediction'], 'blue/pr_curves')

    # Assert that the runs are correct.
    self.assertItemsEqual(
        ['colors', 'mask_every_other_prediction'],
        list(pr_curves_response.keys()))

    # Assert that PR curve data is correct for the colors run.
    entries = pr_curves_response['colors']
    self.assertEqual(3, len(entries))
    self.validatePrCurveEntry(
        expected_step=0,
        expected_precision=[0.3333333, 0.3853211, 0.5421686, 0.75, 1.0],
        expected_recall=[1.0, 0.8400000, 0.3000000, 0.0400000, 0.0],
        pr_curve_entry=entries[0])
    self.validatePrCurveEntry(
        expected_step=1,
        expected_precision=[0.3333333, 0.3855421, 0.5357142, 0.4000000, 1.0],
        expected_recall=[1.0, 0.8533333, 0.3000000, 0.0266666, 0.0],
        pr_curve_entry=entries[1])
    self.validatePrCurveEntry(
        expected_step=2,
        expected_precision=[0.3333333, 0.3934426, 0.5064935, 0.6666666, 1.0],
        expected_recall=[1.0, 0.8000000, 0.2599999, 0.0266666, 0.0],
        pr_curve_entry=entries[2])

    # Assert that PR curve data is correct for the mask_every_other_prediction
    # run.
    entries = pr_curves_response['mask_every_other_prediction']
    self.assertEqual(3, len(entries))
    self.validatePrCurveEntry(
        expected_step=0,
        expected_precision=[0.3333333, 0.3786982, 0.5384616, 1.0, 1.0],
        expected_recall=[1.0, 0.8533334, 0.28, 0.0666667, 0.0],
        pr_curve_entry=entries[0])
    self.validatePrCurveEntry(
        expected_step=1,
        expected_precision=[0.3333333, 0.3850932, 0.5, 0.25, 1.0],
        expected_recall=[1.0, 0.8266667, 0.28, 0.0133333, 0.0],
        pr_curve_entry=entries[1])
    self.validatePrCurveEntry(
        expected_step=2,
        expected_precision=[0.3333333, 0.3986928, 0.4444444, 0.6666667, 1.0],
        expected_recall=[1.0, 0.8133333, 0.2133333, 0.0266666, 0.0],
        pr_curve_entry=entries[2])

  def testPrCurvesRaisesValueErrorWhenNoData(self):
    """Tests that the method for obtaining PR curve data raises a ValueError.

    The handler should raise a ValueError when no PR curve data can be found
    for a certain run-tag combination.
    """
    with six.assertRaisesRegex(
        self, ValueError, r'No PR curves could be fetched'):
      self.plugin.pr_curves_impl(['colors'], 'non_existent_tag')

    with six.assertRaisesRegex(
        self, ValueError, r'No PR curves could be fetched'):
      self.plugin.pr_curves_impl(['non_existent_run'], 'blue/pr_curves')

  def testPluginIsNotActive(self):
    """Tests that the plugin is inactive when no relevant data exists."""
    empty_logdir = os.path.join(self.get_temp_dir(), 'empty_logdir')
    multiplexer = event_multiplexer.EventMultiplexer()
    multiplexer.AddRunsFromDirectory(empty_logdir)
    multiplexer.Reload()
    context = base_plugin.TBContext(
        logdir=empty_logdir, multiplexer=multiplexer)
    plugin = pr_curves_plugin.PrCurvesPlugin(context)
    self.assertFalse(plugin.is_active())

  def testPluginIsActive(self):
    """Tests that the plugin is active when relevant data exists."""
    # The set up for this test generates relevant data.
    self.assertTrue(self.plugin.is_active())


if __name__ == '__main__':
  tf.test.main()
