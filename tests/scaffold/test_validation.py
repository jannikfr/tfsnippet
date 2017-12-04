import os
import unittest

import pytest
import numpy as np
import tensorflow as tf

from tfsnippet.scaffold import early_stopping, get_default_session_or_error
from tfsnippet.utils import TemporaryDirectory


def get_variable_values(variables):
    sess = get_default_session_or_error()
    return sess.run(variables)


def set_variable_values(variables, values):
    sess = get_default_session_or_error()
    sess.run([tf.assign(v, a) for v, a in zip(variables, values)])


def _populate_variables():
    a = tf.get_variable('a', shape=(), dtype=tf.int32)
    b = tf.get_variable('b', shape=(), dtype=tf.int32)
    c = tf.get_variable('c', shape=(), dtype=tf.int32)
    set_variable_values([a, b, c], [1, 2, 3])
    return [a, b, c]


class EarlyStoppingTestCase(tf.test.TestCase):

    def test_prerequisites(self):
        with self.test_session():
            a, b, c = _populate_variables()
            self.assertEqual(get_variable_values([a, b, c]), [1, 2, 3])

    def test_param_vars_must_not_be_empty(self):
        with self.test_session():
            with pytest.raises(
                    ValueError, message='`param_vars` must not be empty'):
                with early_stopping([]):
                    pass

    def test_early_stopping_context_without_updating_loss(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with early_stopping([a, b]):
                set_variable_values([a], [10])
            self.assertEqual(get_variable_values([a, b, c]), [10, 2, 3])

    def test_the_first_loss_will_always_cause_saving(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with early_stopping([a, b]) as es:
                set_variable_values([a], [10])
                self.assertTrue(es.update(1.))
                set_variable_values([a, b], [100, 20])
            self.assertAlmostEqual(es.best_metric, 1.)
            self.assertEqual(get_variable_values([a, b, c]), [10, 2, 3])

    def test_memorize_the_best_loss(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with early_stopping([a, b]) as es:
                set_variable_values([a], [10])
                self.assertTrue(es.update(1.))
                self.assertAlmostEqual(es.best_metric, 1.)
                set_variable_values([a, b], [100, 20])
                self.assertTrue(es.update(.5))
                self.assertAlmostEqual(es.best_metric, .5)
                set_variable_values([a, b, c], [1000, 200, 30])
                self.assertFalse(es.update(.8))
                self.assertAlmostEqual(es.best_metric, .5)
            self.assertAlmostEqual(es.best_metric, .5)
            self.assertEqual(get_variable_values([a, b, c]), [100, 20, 30])

    def test_initial_loss(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with early_stopping([a, b], initial_metric=.6) as es:
                set_variable_values([a], [10])
                self.assertFalse(es.update(1.))
                self.assertAlmostEqual(es.best_metric, .6)
                set_variable_values([a, b], [100, 20])
                self.assertTrue(es.update(.5))
                self.assertAlmostEqual(es.best_metric, .5)
            self.assertEqual(get_variable_values([a, b, c]), [100, 20, 3])

    def test_initial_loss_is_tensor(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with early_stopping([a, b], initial_metric=tf.constant(.5)) as es:
                np.testing.assert_equal(es.best_metric, .5)

    def test_do_not_restore_on_error(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with pytest.raises(ValueError, message='value error'):
                with early_stopping([a, b], restore_on_error=False) as es:
                    self.assertTrue(es.update(1.))
                    set_variable_values([a, b], [10, 20])
                    raise ValueError('value error')
            self.assertAlmostEqual(es.best_metric, 1.)
            self.assertEqual(get_variable_values([a, b, c]), [10, 20, 3])

    def test_restore_on_error(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with pytest.raises(ValueError, message='value error'):
                with early_stopping([a, b], restore_on_error=True) as es:
                    self.assertTrue(es.update(1.))
                    set_variable_values([a, b], [10, 20])
                    raise ValueError('value error')
            self.assertAlmostEqual(es.best_metric, 1.)
            self.assertEqual(get_variable_values([a, b, c]), [1, 2, 3])

    def test_bigger_is_better(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with early_stopping([a, b], smaller_is_better=False) as es:
                set_variable_values([a], [10])
                self.assertTrue(es.update(.5))
                self.assertAlmostEqual(es.best_metric, .5)
                set_variable_values([a, b], [100, 20])
                self.assertTrue(es.update(1.))
                self.assertAlmostEqual(es.best_metric, 1.)
                set_variable_values([a, b, c], [1000, 200, 30])
                self.assertFalse(es.update(.8))
                self.assertAlmostEqual(es.best_metric, 1.)
            self.assertAlmostEqual(es.best_metric, 1.)
            self.assertEqual(get_variable_values([a, b, c]), [100, 20, 30])

    def test_cleanup_checkpoint_dir(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with TemporaryDirectory() as tempdir:
                checkpoint_dir = os.path.join(tempdir, '1')
                with early_stopping([a, b], checkpoint_dir=checkpoint_dir) as es:
                    self.assertTrue(es.update(1.))
                    self.assertTrue(
                        os.path.exists(os.path.join(checkpoint_dir, 'latest')))
                self.assertFalse(os.path.exists(checkpoint_dir))

    def test_not_cleanup_checkpoint_dir(self):
        with self.test_session():
            a, b, c = _populate_variables()
            with TemporaryDirectory() as tempdir:
                checkpoint_dir = os.path.join(tempdir, '2')
                with early_stopping([a, b], checkpoint_dir=checkpoint_dir,
                                    cleanup=False) as es:
                    self.assertTrue(es.update(1.))
                    self.assertTrue(
                        os.path.exists(os.path.join(checkpoint_dir, 'latest')))
                self.assertTrue(
                    os.path.exists(os.path.join(checkpoint_dir, 'latest')))


if __name__ == '__main__':
    unittest.main()