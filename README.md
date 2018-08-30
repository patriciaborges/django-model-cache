# django-model-cache

An easy-to-use cache for Django models.

This code has been developed and used in a production environment for one year.

## How to use
There follows some examples of use. For further examples, see `tests/simple/tests.py`.

```python
class Brand(models.Model):
    name = models.CharField(max_length=128)

    cache = CacheController(timeout=None)


class Product(models.Model):
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    brand = models.ForeignKey('Brand')
    name = models.CharField(max_length=255)

    cache = CacheController(fields=['code', ('brand_id', 'name')], related_fields=['brand'], timeout=None)

    class Meta:
        unique_together = ('name', 'brand')


# Get a product by pk.
product = Product.cache.get(pk=1)

# Get a product by a unique key.
product = Product.cache.get(code='A001')

# Load the related models.
product.load_related()
```

## How to test

Just run `tox` or install the dependencies and run `cd tests/ && ./manage.py test`.
