import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status

from api.v1.endpoints.purchase_products import PurchaseProducts, Item
from crud.schemas import SaleItemCreate


class TestPurchaseProductsInitialize:
    @pytest.mark.asyncio
    async def test_should_initialize_empty_purchase_lists(self):
        purchase = PurchaseProducts()
        await purchase.initialize()
        assert purchase.failed_purchases == []
        assert purchase.successful_purchases == []


class TestPurchaseProductsPurchaseProduct:
    @pytest.mark.asyncio
    async def test_should_add_to_failed_purchases_when_product_not_found(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.failed_purchases = []
        purchase.successful_purchases = []
        
        with patch("api.v1.endpoints.purchase_products.crud.product.get_active", return_value=None):
            item = Item(product_id=9999, quantity=1)
            await purchase.purchase_product(item)
            
        assert len(purchase.failed_purchases) == 1
        assert purchase.failed_purchases[0].product_id == 9999
        assert len(purchase.successful_purchases) == 0

    @pytest.mark.asyncio
    async def test_should_add_to_failed_purchases_when_no_inventory(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.failed_purchases = []
        purchase.successful_purchases = []
        
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.price = Decimal("99.99")
        mock_product.quantity = 100
        
        with patch("api.v1.endpoints.purchase_products.crud.product.get_active", return_value=mock_product):
            with patch("api.v1.endpoints.purchase_products.crud.inventory.get_by_product_id", return_value=[]):
                item = Item(product_id=1, quantity=1)
                await purchase.purchase_product(item)
                
        assert len(purchase.failed_purchases) == 1
        assert len(purchase.successful_purchases) == 0

    @pytest.mark.asyncio
    async def test_should_add_to_failed_purchases_when_insufficient_inventory(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.failed_purchases = []
        purchase.successful_purchases = []
        
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.price = Decimal("99.99")
        mock_product.quantity = 100
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 5
        
        with patch("api.v1.endpoints.purchase_products.crud.product.get_active", return_value=mock_product):
            with patch("api.v1.endpoints.purchase_products.crud.inventory.get_by_product_id", return_value=[mock_inventory]):
                item = Item(product_id=1, quantity=10)
                await purchase.purchase_product(item)
                
        assert len(purchase.failed_purchases) == 1
        assert len(purchase.successful_purchases) == 0

    @pytest.mark.asyncio
    async def test_should_process_purchase_when_sufficient_inventory_in_single_batch(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.failed_purchases = []
        purchase.successful_purchases = []
        
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.price = Decimal("99.99")
        mock_product.quantity = 100
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 50
        mock_inventory.created_at = datetime.utcnow()
        
        with patch("api.v1.endpoints.purchase_products.crud.product.get_active", return_value=mock_product):
            with patch("api.v1.endpoints.purchase_products.crud.inventory.get_by_product_id", return_value=[mock_inventory]):
                with patch("api.v1.endpoints.purchase_products.crud.inventory.bulk_update", return_value=None):
                    with patch("api.v1.endpoints.purchase_products.crud.product.update", return_value=None):
                        item = Item(product_id=1, quantity=10)
                        await purchase.purchase_product(item)
                        
        assert len(purchase.failed_purchases) == 0
        assert len(purchase.successful_purchases) == 1
        assert purchase.successful_purchases[0].product_id == 1
        assert purchase.successful_purchases[0].quantity == 10
        assert purchase.successful_purchases[0].price_per_unit == Decimal("99.99")
        assert mock_inventory.quantity == 40

    @pytest.mark.asyncio
    async def test_should_process_purchase_across_multiple_inventory_batches(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.failed_purchases = []
        purchase.successful_purchases = []
        
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.price = Decimal("99.99")
        mock_product.quantity = 100
        
        mock_inventory_1 = MagicMock()
        mock_inventory_1.quantity = 5
        mock_inventory_1.created_at = datetime(2024, 1, 1)
        
        mock_inventory_2 = MagicMock()
        mock_inventory_2.quantity = 20
        mock_inventory_2.created_at = datetime(2024, 2, 1)
        
        with patch("api.v1.endpoints.purchase_products.crud.product.get_active", return_value=mock_product):
            with patch("api.v1.endpoints.purchase_products.crud.inventory.get_by_product_id", 
                      return_value=[mock_inventory_1, mock_inventory_2]):
                with patch("api.v1.endpoints.purchase_products.crud.inventory.bulk_update", return_value=None):
                    with patch("api.v1.endpoints.purchase_products.crud.product.update", return_value=None):
                        item = Item(product_id=1, quantity=15)
                        await purchase.purchase_product(item)
                        
        assert len(purchase.failed_purchases) == 0
        assert len(purchase.successful_purchases) == 1
        assert mock_inventory_1.quantity == 0
        assert mock_inventory_2.quantity == 10

    @pytest.mark.asyncio
    async def test_should_deplete_entire_inventory_when_exact_match(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.failed_purchases = []
        purchase.successful_purchases = []
        
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.price = Decimal("99.99")
        mock_product.quantity = 100
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 10
        mock_inventory.created_at = datetime.utcnow()
        
        with patch("api.v1.endpoints.purchase_products.crud.product.get_active", return_value=mock_product):
            with patch("api.v1.endpoints.purchase_products.crud.inventory.get_by_product_id", return_value=[mock_inventory]):
                with patch("api.v1.endpoints.purchase_products.crud.inventory.bulk_update", return_value=None):
                    with patch("api.v1.endpoints.purchase_products.crud.product.update", return_value=None):
                        item = Item(product_id=1, quantity=10)
                        await purchase.purchase_product(item)
                        
        assert mock_inventory.quantity == 0
        assert len(purchase.successful_purchases) == 1


class TestPurchaseProductsPurchaseProducts:
    @pytest.mark.asyncio
    async def test_should_process_multiple_items(self):
        purchase = PurchaseProducts()
        purchase.request_data = MagicMock()
        purchase.request_data.items = [
            Item(product_id=1, quantity=1),
            Item(product_id=2, quantity=2),
        ]
        
        call_count = 0
        async def mock_purchase_product(item):
            nonlocal call_count
            call_count += 1
            
        purchase.purchase_product = mock_purchase_product
        await purchase.purchase_products()
        
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_should_handle_empty_items_list(self):
        purchase = PurchaseProducts()
        purchase.request_data = MagicMock()
        purchase.request_data.items = []
        
        call_count = 0
        async def mock_purchase_product(item):
            nonlocal call_count
            call_count += 1
            
        purchase.purchase_product = mock_purchase_product
        await purchase.purchase_products()
        
        assert call_count == 0


class TestPurchaseProductsCreateSalesData:
    @pytest.mark.asyncio
    async def test_should_create_sale_with_successful_purchases(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        
        mock_sale_item_1 = MagicMock()
        mock_sale_item_1.sale_id = 0
        mock_sale_item_1.product_id = 1
        mock_sale_item_1.quantity = 2
        mock_sale_item_1.price_per_unit = Decimal("50.00")
        
        mock_sale_item_2 = MagicMock()
        mock_sale_item_2.sale_id = 0
        mock_sale_item_2.product_id = 2
        mock_sale_item_2.quantity = 1
        mock_sale_item_2.price_per_unit = Decimal("99.99")
        
        purchase.successful_purchases = [mock_sale_item_1, mock_sale_item_2]
        
        mock_sale = MagicMock()
        mock_sale.id = 1
        mock_sale.to_dict.return_value = {"id": 1, "total_amount": Decimal("199.99")}
        
        mock_returned_item_1 = MagicMock()
        mock_returned_item_1.to_dict.return_value = {"id": 1, "product_id": 1}
        mock_returned_item_2 = MagicMock()
        mock_returned_item_2.to_dict.return_value = {"id": 2, "product_id": 2}
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": 1}}
            with patch("api.v1.endpoints.purchase_products.crud.sale.create", return_value=mock_sale):
                with patch("api.v1.endpoints.purchase_products.crud.sale_item.bulk_create", 
                          return_value=[mock_returned_item_1, mock_returned_item_2]):
                    await purchase.create_sales_data()
                    
        assert purchase.sale.id == 1
        assert mock_sale_item_1.sale_id == 1
        assert mock_sale_item_2.sale_id == 1

    @pytest.mark.asyncio
    async def test_should_calculate_total_amount_correctly(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.successful_purchases = [
            SaleItemCreate(sale_id=0, product_id=1, quantity=2, price_per_unit=Decimal("25.00")),
            SaleItemCreate(sale_id=0, product_id=2, quantity=3, price_per_unit=Decimal("10.00")),
        ]
        
        mock_sale = MagicMock()
        mock_sale.id = 1
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": 1}}
            with patch("api.v1.endpoints.purchase_products.crud.sale.create") as mock_create:
                with patch("api.v1.endpoints.purchase_products.crud.sale_item.bulk_create", return_value=[]):
                    await purchase.create_sales_data()
                    created_sale = mock_create.call_args[1]["obj_in"]
                    assert created_sale.total_amount == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_should_handle_empty_successful_purchases(self):
        purchase = PurchaseProducts()
        purchase.db = AsyncMock()
        purchase.successful_purchases = []
        
        mock_sale = MagicMock()
        mock_sale.id = 1
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": 1}}
            with patch("api.v1.endpoints.purchase_products.crud.sale.create") as mock_create:
                with patch("api.v1.endpoints.purchase_products.crud.sale_item.bulk_create", return_value=[]):
                    await purchase.create_sales_data()
                    created_sale = mock_create.call_args[1]["obj_in"]
                    assert created_sale.total_amount == Decimal("0.00")


class TestPurchaseProductsGenerateResponse:
    @pytest.mark.asyncio
    async def test_should_generate_success_response(self):
        purchase = PurchaseProducts()
        purchase.sale = MagicMock()
        purchase.sale.to_dict.return_value = {"id": 1, "total_amount": Decimal("199.99")}
        purchase.successful_purchases = []
        purchase.failed_purchases = []
        
        await purchase.generate_response()
        
        assert purchase.status_code == status.HTTP_200_OK
        assert purchase.response_message == "Products purchased successfully"
        assert "id" in purchase.response_data
        assert "purchased_items" in purchase.response_data
        assert "failed_items" in purchase.response_data

    @pytest.mark.asyncio
    async def test_should_include_failed_items_in_response(self):
        purchase = PurchaseProducts()
        purchase.sale = MagicMock()
        purchase.sale.to_dict.return_value = {"id": 1}
        purchase.successful_purchases = []
        purchase.failed_purchases = [Item(product_id=999, quantity=1)]
        
        await purchase.generate_response()
        
        assert len(purchase.response_data["failed_items"]) == 1


class TestPurchaseProductsProcessFlow:
    @pytest.mark.asyncio
    async def test_should_execute_full_process_flow(self):
        purchase = PurchaseProducts()
        purchase.request_data = MagicMock()
        purchase.request_data.items = []
        
        initialize_called = False
        purchase_products_called = False
        create_sales_data_called = False
        generate_response_called = False
        
        async def mock_initialize():
            nonlocal initialize_called
            initialize_called = True
            purchase.failed_purchases = []
            purchase.successful_purchases = []
            
        async def mock_purchase_products():
            nonlocal purchase_products_called
            purchase_products_called = True
            
        async def mock_create_sales_data():
            nonlocal create_sales_data_called
            create_sales_data_called = True
            purchase.sale = MagicMock()
            purchase.sale.to_dict.return_value = {"id": 1}
            
        async def mock_generate_response():
            nonlocal generate_response_called
            generate_response_called = True
            purchase.status_code = status.HTTP_200_OK
            purchase.response_message = "Products purchased successfully"
            purchase.response_data = {}
        
        purchase.initialize = mock_initialize
        purchase.purchase_products = mock_purchase_products
        purchase.create_sales_data = mock_create_sales_data
        purchase.generate_response = mock_generate_response
        
        await purchase.process_flow()
        
        assert initialize_called
        assert purchase_products_called
        assert create_sales_data_called
        assert generate_response_called


class TestPurchaseProductsClassAttributes:
    def test_should_have_correct_api_configuration(self):
        assert PurchaseProducts.api_name == "purchase_products"
        assert PurchaseProducts.api_url == "purchase_products"
        assert PurchaseProducts.authentication_required is True

    def test_should_have_request_and_response_schemas(self):
        from api.v1.schemas.purchase_products import PurchaseProductsRequest, PurchaseProductsResponse
        assert PurchaseProducts.request_schema == PurchaseProductsRequest
        assert PurchaseProducts.response_schema == PurchaseProductsResponse
