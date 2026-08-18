# Research Findings — Flutter Dev Skill

## Skill Authoring Rules (from official docs)

- YAML frontmatter requires `name` and `description` fields
- `description` max 1,024 chars; must be third-person; describes what the skill does AND when to use it
- Body loads on demand — keep under 500 lines; overflow into sibling files (no nested references)
- Use imperative tone: "Use X", "Never do Y", "Prefer Z over W"
- Provide concrete code examples over abstract descriptions
- Only add context Claude does not already have from training — challenge every paragraph
- Avoid time-sensitive information
- SKILL.md = reusable domain knowledge; CLAUDE.md = project-specific facts (packages installed, CI commands)

---

## Dart Style (Effective Dart)

**Naming**
- Classes, enums, typedefs: `UpperCamelCase`
- Files, packages, directories: `lowercase_with_underscores`
- Variables, functions, parameters: `lowerCamelCase`
- Constants: `lowerCamelCase` (not SCREAMING_CAPS)
- Acronyms >2 letters treated as words: `HttpRequest` not `HTTPRequest`
- No Hungarian notation; no leading underscores on non-private identifiers

**Imports** — order: `dart:` → `package:` → relative; blank line between groups; alphabetical within groups. Relative imports within `lib/`. Never import from another package's `src/`.

**Formatting** — `dart format` is canonical. Lines ≤80 chars preferred.

**Null safety** — Never explicitly initialize to `null`. Use `rethrow` not `throw e`. Never bare `catch` without `on` clause.

**Collections** — `.isEmpty`/`.isNotEmpty` not `.length == 0`. Collection literals over constructors. Prefer `for` over `forEach`. Use `whereType<T>()` for type filtering.

**Async** — `async`/`await` over raw futures. Do not add `async` when just returning a future. Avoid `Completer` except for low-level primitives.

**Strings** — interpolation over `+`. `$name` not `${name}` for simple identifiers. `StringBuffer` for building in loops.

---

## State Management (2026)

**Decision table:**

| Situation | Choice |
|---|---|
| New project, default | Riverpod with code generation |
| Large team, fintech/healthcare, audit trails | Bloc |
| Legacy codebase only | Provider (do not start new projects) |
| Isolated UI toggle | ValueNotifier |

Mixed is legitimate: Bloc for transactional flows (auth, payments), Riverpod for UI state, ValueNotifier for isolated toggles.

**Riverpod with code generation (recommended default):**
- Runtime: `flutter_riverpod`, `riverpod_annotation`
- Dev: `riverpod_generator`, `build_runner`, `riverpod_lint`, `custom_lint`
- All `@riverpod` providers auto-dispose by default; use `@Riverpod(keepAlive: true)` for persistent state
- Use `ref.watch(provider.select((s) => s.field))` to avoid unrelated rebuilds
- Providers at top level or static members — never inside build methods
- Requires `dart run build_runner watch -d` in dev
- Legacy `StateNotifierProvider`, `ChangeNotifierProvider`, `StateProvider` are deprecated

**Failure modes by approach:**
- Provider: state leaks across screens
- Bloc: event-class bloat
- Riverpod: autoDispose causes unexpected state resets on navigation (fix with keepAlive)

---

## Widget Architecture

- **Composition over inheritance** — never subclass widgets for UI reuse
- **Const constructors everywhere** — Flutter skips rebuilds entirely; 20–30% startup improvement
- **Prefer StatelessWidget over helper methods** — helper methods do not create rebuild isolation
- **Keep build() pure** — no HTTP calls, side effects, heavy computation
- **Scope setState() to smallest subtree** — never at top-level screen for localized changes
- **Extract widgets when build() exceeds ~100–150 lines**
- **Flatten nesting** — `Padding` not `Container` for spacing; `SizedBox` for fixed gaps (supports const)

---

## Antipatterns (16 named)

1. **Forgetting dispose()** — `TextEditingController`, `AnimationController`, `ScrollController`, `StreamSubscription`, `FocusNode` all need dispose()
2. **Full-screen setState** — scope to the subtree that actually changes
3. **setState after async without mounted check** — `if (mounted) setState(...)`
4. **Navigation after async without mounted check** — `if (!mounted) return;` before any Navigator call
5. **BuildContext in initState()** — defer via `WidgetsBinding.instance.addPostFrameCallback`
6. **New future inside FutureBuilder** — fires on every rebuild; cache in initState()
7. **Business logic in widgets** — belongs in ViewModel/Notifier/Bloc layer
8. **GlobalKey as state management workaround** — use proper state management
9. **Opacity widget on complex trees** — forces saveLayer(); use AnimatedOpacity or color opacity directly
10. **Static subtrees inside AnimatedBuilder.builder** — pass as `child` parameter; built once not every tick
11. **ListView without builder** — use ListView.builder for any non-trivial list
12. **Overriding operator== on widgets** — O(N²), prevents compiler optimizations (official warning)
13. **Unoptimized images** — always set cacheWidth/cacheHeight; use cached_network_image for network
14. **Empty catch or swallowed stack traces** — always log with stack; use rethrow
15. **didChangeDependencies without init guard** — use `bool _isInitialized` flag
16. **Calling setState inside build()** — never

---

## Project Structure (Feature-First MVVM — 2026 Standard)

```
lib/
├── core/                   # Never depends on features
│   ├── di/
│   ├── network/
│   ├── utils/
│   └── theme/
├── features/
│   └── auth/
│       ├── presentation/
│       │   ├── screens/
│       │   ├── widgets/
│       │   └── view_models/
│       ├── data/
│       │   ├── models/         # DTOs
│       │   ├── services/       # Thin API wrappers
│       │   └── repositories/   # Concrete implementation
│       └── domain/             # Optional — only for complex cross-repo logic
│           ├── entities/
│           ├── repositories/   # Abstract contracts
│           └── use_cases/
└── shared/                 # Widgets and models used across features
```

Dependency direction (inward only): `View → ViewModel → Repository → Service`

Layer rules:
- **View**: display logic only — conditional rendering, animations, layout. No business logic.
- **ViewModel**: state management, business logic, exposes commands for UI
- **Repository**: single source of truth, caching, error handling, retry, merges data sources
- **Service**: thin wrapper around external APIs; returns Future/Stream
- **Domain layer**: add only when merging data from multiple repositories or complex reusable logic

---

## Linting

- Baseline: `flutter_lints` (official, all projects)
- Stricter: `very_good_analysis` (enterprise — adopt from project start, not mid-project)
- Add `riverpod_lint` + `custom_lint` when using Riverpod
- Exclude `*.g.dart`, `*.freezed.dart` in `analysis_options.yaml`
- Fail CI on lint errors

---

## Testing

| Type | Package | Scope |
|---|---|---|
| Unit | `test` + `mocktail` | Business logic, repositories, services |
| Widget | `flutter_test` | Rendering and interaction |
| Integration | `patrol` | End-to-end, native platform UI |
| Golden | `alchemist` | Visual regression |

- Prioritize unit and widget tests; integration tests for critical flows only
- Every test must have at least one `expect()`

---

## Key Gotchas

- **Riverpod autoDispose default**: navigating away and back rebuilds provider from scratch unless `keepAlive: true`
- **BuildContext in initState**: unsafe — defer via addPostFrameCallback
- **FutureBuilder inline future**: fires new request every parent rebuild — always cache in initState()
- **mounted check placement**: check `if (!mounted) return;` immediately after every `await` — one check at top is insufficient for multiple awaits
- **build_runner required**: generated `*.g.dart` files must be committed; project won't compile without them
- **very_good_analysis mid-project**: significant lint noise upfront on adoption
- **operator== on widgets**: explicitly warned against in official docs

---

## Code Examples

### Riverpod providers (code gen)
```dart
@riverpod
Dio dio(DioRef ref) => Dio();

@Riverpod(keepAlive: true)
AuthRepository authRepository(AuthRepositoryRef ref) =>
    AuthRepositoryImpl(ref.watch(dioProvider));

@riverpod
Future<List<Note>> notes(NotesRef ref) =>
    ref.watch(notesRepositoryProvider).fetchAll();

@riverpod
class NotesViewModel extends _$NotesViewModel {
  @override
  Future<List<Note>> build() async =>
      ref.watch(notesRepositoryProvider).fetchAll();

  Future<void> deleteNote(String id) async {
    await ref.read(notesRepositoryProvider).delete(id);
    ref.invalidateSelf();
  }
}

// Select to avoid unrelated rebuilds
final count = ref.watch(
  notesViewModelProvider.select((s) => s.valueOrNull?.length ?? 0),
);
```

### Async with mounted check
```dart
Future<void> _loadAndNavigate() async {
  final result = await fetchData();
  if (!mounted) return;
  setState(() { _data = result; });
  if (!mounted) return;
  Navigator.of(context).pushNamed('/detail');
}
```

### AnimatedBuilder with static child
```dart
// Wrong — ExpensiveWidget rebuilt every tick
AnimatedBuilder(
  animation: _controller,
  builder: (context, child) => Column(children: [
    ExpensiveWidget(),
    Transform.scale(scale: _animation.value, child: const AnimatedPart()),
  ]),
);

// Correct — ExpensiveWidget built once
AnimatedBuilder(
  animation: _controller,
  child: const ExpensiveWidget(),
  builder: (context, child) => Column(children: [
    child!,
    Transform.scale(scale: _animation.value, child: const AnimatedPart()),
  ]),
);
```
