import backend.main as main


def test_paypal_payment_initiation_has_production_composer():
    composer = getattr(
        main,
        "_compose_customer_paypal_payment_initiation_runtime",
        None,
    )

    assert callable(composer)


def test_paypal_payment_initiation_runtime_has_idempotent_gate():
    assert hasattr(
        main,
        "_customer_paypal_payment_initiation_runtime_composed",
    )
