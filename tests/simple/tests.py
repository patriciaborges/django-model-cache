from simple.models import Product, Brand
from django.test import TransactionTestCase
import uuid


class CacheManagerTest(TransactionTestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name='Apple')
        self.product = Product.objects.create(brand=self.brand, name='iPhone X Black 256GB')
        self.product_2 = Product.objects.create(brand=self.brand, name='iPhone 8 Black 256GB')

    def test_there_is_cache_attr(self):
        self.assertIsNotNone(getattr(Product, 'cache'))

    def test_load_from_cache(self):
        with self.assertNumQueries(0):
            product = Product.cache.get(id=self.product.id)

        self.assertEquals(product, self.product)

    def test_check_field_values(self):
        objs = [self.brand, self.product]

        with self.assertNumQueries(0):
            for obj in objs:
                obj_from_cache = obj.__class__.cache.get(id=obj.id)

                for field in obj.__class__._meta.local_fields:
                    value1 = getattr(obj_from_cache, field.attname)
                    value2 = getattr(obj, field.attname)
                    self.assertEquals(value1, value2)

    def test_check_update_model_and_load_an_old_cache_object(self):
        old_name = self.product.name
        key = Product.cache._make_key(**{'pk': self.product.pk})
        Product.cache._cache.set(key, self.product)
        self.assertEquals(old_name, self.product.name)
        self.product.name = 'new'
        self.product.save()
        product = Product.cache.get(pk=self.product.pk)
        self.assertEquals(product.name, self.product.name)

    def test_load_related(self):
        with self.assertNumQueries(0):
            self.product.load_related()

        self.assertEquals(self.product.brand, self.brand)

    def test_get_by_other_key(self):
        with self.assertNumQueries(0):
            product = Product.cache.get(code=self.product.code)

        self.assertEquals(product, self.product)

    def test_get_or_none(self):
        self.assertIsNone(Product.cache.get_or_none(code=uuid.uuid4()))
        self.assertIsNotNone(Product.cache.get_or_none(code=self.product.code))

    def test_get_key_tuple(self):
        product = Product.cache.get(name=self.product.name, brand_id=self.product.brand_id)
        self.assertEquals(product, self.product)

    def test_makes_db_query_when_there_is_no_cache(self):

        Product.cache._delete_cache(self.product)
        with self.assertNumQueries(1):
            product = Product.cache.get(id=self.product.id)

        self.assertEquals(product, self.product)

    def test_delete_object(self):
        from django.core.cache import caches

        product_id = self.product.id
        self.product.delete()

        with self.assertNumQueries(1):
            with self.assertRaises(Product.DoesNotExist):
                Product.cache.get(id=product_id)

        key = Product.cache._make_key(**{'pk': product_id})
        self.assertIsNone(caches['default'].get(key))

    def test_get_multiple(self):
        def make_qs():
            return Product.objects.filter(brand=self.brand)

        Product.cache.delete_cache_multiple('apple_products')

        with self.assertNumQueries(1):
            objs = Product.cache.get_multiple('apple_products', make_qs(), timeout=3600)
            self.assertEqual(len(objs), 2)

        with self.assertNumQueries(0):
            objs = Product.cache.get_multiple('apple_products', make_qs(), timeout=3600)

            self.assertEqual(len(objs), 2)
            self.assertEqual(set(objs), set([self.product, self.product_2]))

        Product.cache.delete_cache_multiple('apple_products')
        with self.assertNumQueries(1):
            objs = Product.cache.get_multiple('apple_products', make_qs(), timeout=3600)
