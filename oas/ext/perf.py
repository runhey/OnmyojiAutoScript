import time


def pretty_time(second):
    """Format time with adaptive units (s or ms or us)

    Inlined from alasio.base.pretty (OAS has no oas.base.pretty yet).

    Args:
        second (float): Time in seconds

    Returns:
        str: Formatted time string
    """
    if second >= 1:
        return f'{second:.3f}s'
    if second >= 0.001:
        return f"{second * 1000:.3f}ms"
    return f"{second * 1000000:.3f}us"


class PerformanceTest:
    """Performance testing framework"""

    def __init__(self):
        self.functions = []  # Store registered functions and parameters
        self.min_duration = 0.3  # Minimum runtime (seconds)
        self.min_iterations = 15  # Minimum iterations
        self.outputs_consistent = True  # Track output consistency

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.functions:
            self.run_all_tests()

    def register(self, func, *args, **kwargs):
        """
        Register function and parameters

        Args:
            func: Function to register
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """

        # Create local function to avoid unpacking args at runtime
        def local_func():
            return func(*args, **kwargs)

        # Store parameter information for display
        param_info = self._format_parameters(args, kwargs)

        self.functions.append({
            'func': local_func,
            'name': func.__name__,
            'params': param_info,
            'args': args,
            'kwargs': kwargs
        })
        print(f"Registered function: {func.__name__}{param_info}")

    def _format_parameters(self, args, kwargs, max_length=120):
        """
        Format function parameters for display based on final string length

        Args:
            args: Positional arguments
            kwargs: Keyword arguments
            max_length: Maximum length for parameter string

        Returns:
            str: Formatted parameter string
        """
        parts = []

        # Format positional arguments
        for arg in args:
            if hasattr(arg, 'shape') and 'numpy' in str(type(arg)):
                # Handle numpy arrays without importing numpy
                parts.append(f"array{getattr(arg, 'shape', '(?)')}")
            else:
                parts.append(str(arg))

        # Format keyword arguments
        for key, value in kwargs.items():
            if hasattr(value, 'shape') and 'numpy' in str(type(value)):
                parts.append(f"{key}=array{getattr(value, 'shape', '(?)')}")
            else:
                parts.append(f"{key}={value}")

        param_str = "(" + ", ".join(parts) + ")" if parts else "()"

        # Final truncation if the entire parameter string is too long
        if len(param_str) > max_length:
            truncated = param_str[:max_length] + "..."
            # Ensure we don't break in the middle of a quote
            if truncated.count("'") % 2 == 1:
                # Find the last complete quote
                last_quote = truncated.rfind("'", 0, -3)
                if last_quote > 0:
                    truncated = param_str[:last_quote] + "..."
            param_str = truncated

        return param_str

    @staticmethod
    def _format_output(output):
        """
        Format output for comparison (supports numpy arrays without importing numpy)
        No sorting to preserve original order

        Args:
            output: Function output to format

        Returns:
            str: Formatted output string
        """
        # Check if it's a numpy array without importing numpy
        # note that numpy.ndarray has no __module__ attribute in some versions,
        # so detection relies on shape and the type string only
        if hasattr(output, 'shape') and 'numpy' in str(type(output)):
            shape = getattr(output, 'shape', 'unknown')
            dtype = getattr(output, 'dtype', 'unknown')

            # For small arrays, show some values
            if hasattr(output, 'size') and getattr(output, 'size', 0) <= 10:
                try:
                    # Convert to list for display
                    values = output.tolist() if hasattr(output, 'tolist') else str(output)
                    return f"array{shape}({values})"
                except Exception:
                    return f"array{shape}[{dtype}]"
            else:
                return f"array{shape}[{dtype}]"

        elif isinstance(output, (list, tuple)):
            # No sorting - preserve original order
            if len(output) < 100:
                return str(output)
            else:
                return f"Sequence length: {len(output)}"
        elif isinstance(output, dict):
            # No sorting - preserve original order (Python 3.7+ maintains insertion order)
            if len(output) < 20:
                return str(output)
            else:
                return f"Dict length: {len(output)}"
        elif isinstance(output, (int, float, str, bool)):
            return str(output)
        else:
            return f"<{type(output).__name__} object>"

    def verify_outputs(self):
        """
        Verify all function outputs are consistent

        Returns:
            bool: True if outputs are consistent
        """
        print("\n" + "=" * 60)
        print("Step 1: Verify function output consistency")
        print("=" * 60)

        outputs = []
        formatted_outputs = []

        for func_info in self.functions:
            try:
                print(f"Running function: {func_info['name']}{func_info['params']}")
                start_time = time.time()
                result = func_info['func']()
                end_time = time.time()

                outputs.append(result)
                formatted_output = self._format_output(result)
                formatted_outputs.append(formatted_output)

                print(f"   Execution time: {pretty_time(end_time - start_time)}")
                print(f"   Output: {formatted_output}")
                print()

            except Exception as e:
                print(f"   Execution failed: {str(e)}")
                self.outputs_consistent = False
                return False

        if len(self.functions) < 2:
            print("Only one function, skipping output consistency check")
            return True

        # Check output consistency
        first_output = formatted_outputs[0]
        all_consistent = all(output == first_output for output in formatted_outputs)

        if all_consistent:
            print("All function outputs are consistent!")
            self.outputs_consistent = True
            return True
        else:
            print("Function outputs are inconsistent!")
            for func_info, output in zip(self.functions, formatted_outputs):
                print(f"   {func_info['name']}{func_info['params']}: {output}")
            self.outputs_consistent = False
            return False

    def estimate_iterations(self):
        """
        Estimate required test iterations for each function

        Returns:
            dict: Mapping of function identifier to required iterations
        """
        print("\n" + "=" * 60)
        print("Step 2: Estimate performance test parameters")
        print("=" * 60)

        iterations_map = {}

        for i, func_info in enumerate(self.functions):
            func_id = f"{func_info['name']}{func_info['params']}"
            print(f"Analyzing function: {func_id}")

            # Progressive estimation to get accurate timing
            func = func_info['func']
            test_iterations = 1

            while True:
                start_time = time.perf_counter()
                for _ in range(test_iterations):
                    func()
                total_time = time.perf_counter() - start_time

                if total_time >= 0.001:  # >= 1ms
                    # Get average time per execution
                    single_duration = total_time / test_iterations
                    break
                else:
                    # If too fast, increase iterations by 10x
                    test_iterations *= 10
                    if test_iterations > 1000000:  # Safety limit
                        single_duration = total_time / test_iterations
                        break

            print(f"   Single execution time: {pretty_time(single_duration)}")

            # Calculate required iterations
            time_based_iterations = max(1, int(self.min_duration / single_duration))
            required_iterations = max(time_based_iterations, self.min_iterations)

            iterations_map[i] = required_iterations  # Use index as key
            estimated_total_time = required_iterations * single_duration

            print(f"   Planned iterations: {required_iterations}")
            print(f"   Estimated total time: {estimated_total_time:.2f}s")
            print()

        return iterations_map

    def run_performance_test(self, iterations_map):
        """
        Execute performance test

        Args:
            iterations_map (dict): Mapping of function index to iterations

        Returns:
            list: Performance test results
        """
        print("\n" + "=" * 60)
        print("Step 3: Execute performance test")
        print("=" * 60)

        results = []

        for i, func_info in enumerate(self.functions):
            func_name = func_info['name']
            func_params = func_info['params']
            iterations = iterations_map[i]

            print(f"Testing function: {func_name}{func_params}")
            print(f"   Iterations: {iterations}")

            # Extract function to avoid dictionary lookup overhead
            func = func_info['func']

            # Performance test (no warm-up, simple loop)
            total_start = time.perf_counter()

            for _ in range(iterations):
                func()

            total_end = time.perf_counter()
            total_time = total_end - total_start

            # Calculate average time
            avg_time = total_time / iterations

            result = {
                'name': func_name,
                'params': func_params,
                'iterations': iterations,
                'avg_time': avg_time
            }
            results.append(result)

            print(f"   Completed!")
            print()

        return results

    def _needs_params_column(self, results):
        """
        Check if we need to display parameters column

        Args:
            results (list): Performance test results

        Returns:
            bool: True if parameters column is needed
        """
        # Check if there are functions with same name but different parameters
        name_counts = {}
        for result in results:
            name = result['name']
            name_counts[name] = name_counts.get(name, 0) + 1

        # If any function name appears more than once, we need params column
        return any(count > 1 for count in name_counts.values())

    def print_results(self, results):
        """
        Print performance test results

        Args:
            results (list): Performance test results
        """
        # Check if we need parameters column
        show_params = self._needs_params_column(results)

        # Calculate adaptive column widths for main data columns
        max_name_length = max(len(result['name']) for result in results)
        name_width = max(20, max_name_length + 2)  # Minimum 20, with padding

        # Sort results by average time (fastest first)
        sorted_results = sorted(results, key=lambda x: x['avg_time'])
        fastest_time = sorted_results[0]['avg_time']

        # Calculate total width for main data columns (excluding parameters)
        main_data_width = name_width + 12 + 12 + 10 + 2  # name + iterations + average + slower + padding

        print("\n" + "=" * main_data_width)
        print("Performance Test Results")
        print("=" * main_data_width)

        # Table header
        header = f"{'Function':<{name_width}} {'Iterations':<12} {'Average':<12} {'Slower':<10}"
        if show_params:
            header += " Parameters"
        print(header)

        # Separator line - only for main data columns
        separator = "-" * main_data_width
        print(separator)

        # Data rows
        for i, result in enumerate(sorted_results):
            row = f"{result['name']:<{name_width}} {result['iterations']:<12} {pretty_time(result['avg_time']):<12}"

            if i == 0:
                # Fastest function - no slower ratio
                row += f" {'(fastest)':<10}"
            else:
                # Calculate slower ratio
                slower_ratio = result['avg_time'] / fastest_time
                row += f" {slower_ratio:.2f}x{'':<{10 - len(f'{slower_ratio:.2f}x')}}"

            if show_params:
                # Parameters can extend beyond the main table width
                row += f" {result['params']}"

            print(row)

        print(separator)

        # Warning if outputs were inconsistent
        if not self.outputs_consistent:
            print("\nWARNING: Function outputs are inconsistent!")
            print("Performance test results may not be meaningful.")

    def run_all_tests(self):
        """Run complete test process"""
        if not self.functions:
            print("No functions registered!")
            return

        print(f"Starting performance test with {len(self.functions)} registered functions")

        # Step 1: Verify output consistency
        self.verify_outputs()

        # Step 2: Estimate test parameters
        iterations_map = self.estimate_iterations()

        # Step 3: Execute performance test
        results = self.run_performance_test(iterations_map)

        # Step 4: Print results
        self.print_results(results)


# Usage example
if __name__ == "__main__":
    # Example functions
    def bubble_sort(arr):
        """Bubble sort algorithm"""
        arr = arr.copy()
        n = len(arr)
        for i in range(n):
            for j in range(0, n - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
        return arr

    def selection_sort(arr):
        """Selection sort algorithm"""
        arr = arr.copy()
        n = len(arr)
        for i in range(n):
            min_idx = i
            for j in range(i + 1, n):
                if arr[j] < arr[min_idx]:
                    min_idx = j
            arr[i], arr[min_idx] = arr[min_idx], arr[i]
        return arr

    def python_sort(arr):
        """Python built-in sort"""
        return sorted(arr)

    # Test with different data types including paths
    small_data = [64, 34, 25, 12, 22, 11, 90]
    large_data = list(range(100, 0, -1))

    # Register functions with different parameter types
    with PerformanceTest() as pref:
        pref.register(bubble_sort, small_data)
        pref.register(bubble_sort, large_data)
        pref.register(selection_sort, small_data)
        pref.register(python_sort, large_data)

    # Example output with simplified parameter display:
    """
    ========================================================
    Performance Test Results
    ========================================================
    Function             Iterations   Average      Slower
    --------------------------------------------------------
    python_sort          549846       0.462us      (fastest)
    selection_sort       38596        7.723us      16.71x
    bubble_sort          29060        10.425us     22.55x
    --------------------------------------------------------
    """
