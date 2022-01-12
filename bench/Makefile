LIBS ?= incant wired di dependency_injector

single_dep:
	@bash -c "for lib in $(LIBS); do echo -n \"Benchmarking \$$lib: \" && pyperf timeit --rigorous -q -s \"from single_dep import \$${lib}_call_func as call_func\" 'call_func()'; done"

two_deps:
	@bash -c "for lib in $(LIBS); do echo -n \"Benchmarking \$$lib: \" && pyperf timeit --rigorous -q -s \"from two_deps import \$${lib}_call_func as call_func\" 'call_func()'; done"