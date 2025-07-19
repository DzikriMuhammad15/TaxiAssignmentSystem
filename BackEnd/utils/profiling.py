import io
import pstats
from datetime import datetime

def print_profile_header():
    print("\n" + "="*100)
    print("PREC INTELLIGENT AGENT PERFORMANCE PROFILE")
    print("="*100)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*100)

def print_profile_summary(stats, total_time):
    print(f"\nPROFILE SUMMARY:")
    print(f"Total execution time: {total_time:.4f} seconds")
    print(f"Total function calls: {stats.total_calls}")
    print(f"Primitive calls: {stats.prim_calls}")
    print("-"*100)

def print_top_functions(stats, limit=20):
    print(f"\nTOP {limit} TIME-CONSUMING FUNCTIONS:")
    print(f"{'Function':<50} {'Calls':<8} {'Total Time':<12} {'Per Call':<12} {'Cumulative':<12} {'%':<6}")
    print("-"*100)
    
    stats_data = []
    for func, (cc, nc, tt, ct, callers) in stats.stats.items():
        filename, line_number, function_name = func
        
        percentage = (tt / stats.total_tt * 100) if stats.total_tt > 0 else 0
        per_call = tt / cc if cc > 0 else 0
        
        stats_data.append({
            'function': f"{function_name} ({filename.split('/')[-1]}:{line_number})",
            'calls': cc,
            'total_time': tt,
            'per_call': per_call,
            'cumulative': ct,
            'percentage': percentage
        })
    
    stats_data.sort(key=lambda x: x['total_time'], reverse=True)
    
    for i, data in enumerate(stats_data[:limit]):
        func_name = data['function'][:48] + '..' if len(data['function']) > 50 else data['function']
        print(f"{func_name:<50} {data['calls']:<8} {data['total_time']:<12.4f} {data['per_call']:<12.6f} {data['cumulative']:<12.4f} {data['percentage']:<6.1f}")

def print_bottleneck_analysis(stats):
    print(f"\nBOTTLENECK ANALYSIS:")
    print("-"*100)
    
    bottlenecks = []
    for func, (cc, nc, tt, ct, callers) in stats.stats.items():
        filename, line_number, function_name = func
        percentage = (tt / stats.total_tt * 100) if stats.total_tt > 0 else 0
        
        if percentage > 5.0:
            bottlenecks.append({
                'function_name': function_name,
                'filename': filename.split('/')[-1],
                'line_number': line_number,
                'calls': cc,
                'total_time': tt,
                'percentage': percentage,
                'per_call': tt / cc if cc > 0 else 0
            })
    
    bottlenecks.sort(key=lambda x: x['percentage'], reverse=True)
    
    if bottlenecks:
        for bottleneck in bottlenecks:
            print(f"\nBOTTLENECK: {bottleneck['function_name']}")
            print(f"File: {bottleneck['filename']}:{bottleneck['line_number']}")
            print(f"Impact: {bottleneck['percentage']:.1f}% of total execution time")
            print(f"Calls: {bottleneck['calls']}")
            print(f"Total time: {bottleneck['total_time']:.4f}s")
            print(f"Time per call: {bottleneck['per_call']:.6f}s")
            
            if bottleneck['percentage'] > 20:
                print(f"CRITICAL: This function consumes {bottleneck['percentage']:.1f}% of execution time!")
                print(f"SUGGESTION: High priority for optimization")
            elif bottleneck['percentage'] > 10:
                print(f"HIGH IMPACT: Consider optimizing this function")
            else:
                print(f"MODERATE IMPACT: Monitor for optimization opportunities")
    else:
        print("No significant bottlenecks detected (no function >5% of total time)")

def print_profile_footer():
    print("\n" + "="*100)
    print("END OF PROFILE ANALYSIS")
    print("="*100 + "\n")

def analyze_and_print_profile(profiler):
    """Comprehensive profile analysis and printing"""
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    
    total_time = 0
    for func, (cc, nc, tt, ct, callers) in stats.stats.items():
        total_time += tt
    
    print_profile_header()
    print_profile_summary(stats, total_time)
    print_top_functions(stats, limit=25)
    print_bottleneck_analysis(stats)
    print_profile_footer()
    
    print("STANDARD CPROFILE OUTPUT:")
    print("-"*50)
    stats.sort_stats('time')
    stats.print_stats(30)
    print("-"*50)
