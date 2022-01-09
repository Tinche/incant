"""Test scenarios from the wired library.

Note: this isn't necessarily idiomatic incant usage, just tests
to prove feature parity.
"""
from collections import defaultdict
from typing import List

from attr import Factory, define

from incant import Incanter


def test_greeter(incanter: Incanter):
    """Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/simple/index.html"""

    @define
    class Greeter:
        greeting: str

        def __call__(self) -> str:
            return f"{self.greeting} !!"

    greeter = Greeter(greeting="Hello")
    incanter.register_hook(lambda p: p.annotation is Greeter, lambda: greeter)

    def greet_a_customer(greeter: Greeter) -> str:
        return greeter()

    assert incanter.invoke(greet_a_customer) == "Hello !!"


def test_greeter_factory(incanter: Incanter):
    """Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/factory/index.html"""

    @define
    class Greeter:
        greeting: str

        def __call__(self) -> str:
            return f"{self.greeting} !!"

    incanter.register_hook(
        lambda p: p.annotation is Greeter, lambda: Greeter(greeting="Hello")
    )

    def greet_a_customer(greeter: Greeter) -> str:
        return greeter()

    assert incanter.invoke(greet_a_customer) == "Hello !!"


def test_greeter_settings():
    """Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/settings/index.html"""

    @define
    class Settings:
        punctuation: str

    @define
    class Greeter:
        greeting: str
        punctuation: str

        def __call__(self) -> str:
            return f"{self.greeting} {self.punctuation}"

    def greet_a_customer(greeter: Greeter) -> str:
        return greeter()

    def setup(settings: Settings):
        incanter = Incanter()
        punctuation = settings.punctuation

        def greeter_factory() -> Greeter:
            return Greeter(greeting="Hello", punctuation=punctuation)

        incanter.register_hook(lambda p: p.annotation is Greeter, greeter_factory)
        return incanter

    settings = Settings(punctuation="!!")
    incanter = setup(settings)
    assert incanter.invoke(greet_a_customer) == "Hello !!"


def test_greeter_settings_idiomatic(incanter: Incanter):
    """
    Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/settings/index.html

    The example is rewritten to be idiomatic incanter.
    """

    @define
    class Greeter:
        greeting: str
        punctuation: str

        def __call__(self) -> str:
            return f"{self.greeting} {self.punctuation}"

    def greet_a_customer(greeter: Greeter) -> str:
        return greeter()

    @incanter.register_by_type
    def greeter_factory(punctuation: str) -> Greeter:
        return Greeter(greeting="Hello", punctuation=punctuation)

    incanter.register_hook(lambda p: p.name == "punctuation", lambda: "!!")

    assert incanter.invoke(greet_a_customer) == "Hello !!"


def test_greeter_contexts(incanter: Incanter):
    """Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/context/index.html"""

    @define
    class Customer:
        name: str

    @define
    class FrenchCustomer(Customer):
        pass

    @define
    class Greeter:
        punctuation: str
        greeting: str = "Hello"

        def __call__(self, customer: Customer) -> str:
            return f"{self.greeting} {customer.name} {self.punctuation}"

    @define
    class FrenchGreeter(Greeter):
        greeting: str = "Bonjour"

        def __call__(self, customer: Customer) -> str:
            return f"{self.greeting} {customer.name} {self.punctuation}"

    def greet_a_customer(customer: Customer, greeter: Greeter):
        return greeter(customer)

    incanter.register_by_name(lambda: "!!", name="punctuation")
    incanter.register_by_type(
        lambda customer, punctuation: FrenchGreeter(punctuation)
        if isinstance(customer, FrenchCustomer)
        else Greeter(punctuation),
        Greeter,
    )

    customer = Customer(name="Mary")
    french_customer = FrenchCustomer(name="Henri")

    assert incanter.invoke(greet_a_customer, customer) == "Hello Mary !!"
    assert incanter.invoke(greet_a_customer, french_customer) == "Bonjour Henri !!"


def test_greeter_decoupled(incanter: Incanter):
    """Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/decoupled/index.html"""

    # The first part of the app:
    @define
    class Customer:
        name: str

    @define
    class Greeter:
        punctuation: str
        greeting: str = "Hello"

        def __call__(self, customer: Customer) -> str:
            return f"{self.greeting} {customer.name} {self.punctuation}"

    incanter.register_by_name(lambda: "!!", name="punctuation")

    customer_types_to_greeters = defaultdict(lambda: Greeter)  # type: ignore

    def greeter_factory(customer, punctuation) -> Greeter:
        return customer_types_to_greeters[type(customer)](punctuation)

    incanter.register_by_type(greeter_factory)

    def greet_a_customer(customer: Customer, greeter: Greeter):
        return greeter(customer)

    customer = Customer(name="Mary")
    assert incanter.invoke(greet_a_customer, customer) == "Hello Mary !!"

    # The second part of the app:
    @define
    class FrenchCustomer(Customer):
        pass

    @define
    class FrenchGreeter(Greeter):
        greeting: str = "Bonjour"

        def __call__(self, customer: Customer) -> str:
            return f"{self.greeting} {customer.name} {self.punctuation}"

    customer_types_to_greeters[FrenchCustomer] = FrenchGreeter

    french_customer = FrenchCustomer(name="Henri")
    assert incanter.invoke(greet_a_customer, french_customer) == "Bonjour Henri !!"


def test_greeter_datastore(incanter: Incanter):
    """Test the wired scenario from https://wired.readthedocs.io/en/latest/tutorial/datastore/index.html"""
    # The first part of the app:
    @define
    class Customer:
        name: str

    @define
    class Datastore:
        customers: List[Customer] = Factory(list)

    @define
    class Greeter:
        punctuation: str
        greeting: str = "Hello"

        def __call__(self, customer: Customer) -> str:
            return f"{self.greeting} {customer.name} {self.punctuation}"

    datastore = Datastore()
    incanter.register_by_name(lambda: "!!", name="punctuation")
    incanter.register_by_type(lambda: datastore, Datastore)

    customer_types_to_greeters = defaultdict(lambda: Greeter)  # type: ignore
    incanter.register_by_type(
        lambda customer, punctuation: customer_types_to_greeters[type(customer)](
            punctuation
        ),
        Greeter,
    )

    customer = Customer(name="Mary")
    datastore.customers.append(customer)

    def customer_interaction(customer: Customer, greeter: Greeter):
        return greeter(customer)

    # The second part of the app:
    @define
    class FrenchCustomer(Customer):
        pass

    @define
    class FrenchGreeter(Greeter):
        greeting: str = "Bonjour"

        def __call__(self, customer: Customer) -> str:
            return f"{self.greeting} {customer.name} {self.punctuation}"

    customer_types_to_greeters[FrenchCustomer] = FrenchGreeter

    french_customer = FrenchCustomer(name="Henri")

    def add_to_datastore(datastore: Datastore):
        datastore.customers.append(french_customer)

    incanter.invoke(add_to_datastore)

    def sample_interactions(incanter: Incanter) -> List[str]:
        """Pretend to do a couple of customer interactions"""

        greetings = []

        def get_customers(datastore: Datastore) -> List[Customer]:
            return list(datastore.customers)

        customers = incanter.invoke(get_customers)

        for customer in customers:
            greeting = incanter.invoke(customer_interaction, customer)
            greetings.append(greeting)

        return greetings

    assert sample_interactions(incanter) == ["Hello Mary !!", "Bonjour Henri !!"]
