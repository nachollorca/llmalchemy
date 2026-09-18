# CHANGELOG

<!-- version list -->

## v1.8.0 (2026-09-18)

### Features

- **agent**: Open one trace per agent run
  ([`093794f`](https://github.com/nachollorca/llmalchemy/commit/093794f462eaef0f5bf72df24f9aaf2f5f14049b))


## v1.7.0 (2026-09-18)

### Bug Fixes

- **agent**: Make the execution result format properly
  ([`eb76468`](https://github.com/nachollorca/llmalchemy/commit/eb76468d1b45115eb876fcc361c0f2a4702d4b7a))

### Features

- **core**: Emit database changes event
  ([`c80d481`](https://github.com/nachollorca/llmalchemy/commit/c80d481f1b9151440976622ccd099c51b09c9541))


## v1.6.0 (2026-09-17)

### Documentation

- **readme**: Add link to lewis ellis video
  ([`9c47e0a`](https://github.com/nachollorca/llmalchemy/commit/9c47e0a8226565525a13c4115151264ec997fd0d))

### Features

- **core**: Explain transactional model
  ([`50fceb6`](https://github.com/nachollorca/llmalchemy/commit/50fceb65277edf5fc7d8d3e1089457901aaf2ce4))


## v1.5.1 (2026-09-17)

### Bug Fixes

- Drop stale engine finalizer from deserialize after new_session refactor
  ([`9f822cc`](https://github.com/nachollorca/llmalchemy/commit/9f822cc110c786de6d133995ac31f8a4661028c0))

### Code Style

- Lint
  ([`ee7243c`](https://github.com/nachollorca/llmalchemy/commit/ee7243c024708e76d742af510a2a5637371e0a5f))


## v1.5.0 (2026-09-16)

### Features

- **core**: Wire up lmdk native thinking
  ([`d56b65f`](https://github.com/nachollorca/llmalchemy/commit/d56b65f309c75ae13baafc9ce3a9f5bc0d2b2f6a))


## v1.4.2 (2026-08-10)

### Bug Fixes

- Enforce SQLite foreign keys on the sessions llmalchemy creates
  ([`7d39fbf`](https://github.com/nachollorca/llmalchemy/commit/7d39fbf1bdfce1f7ed4ed25d8e8acd2d2dd0cf21))

### Continuous Integration

- Pass --frozen to all uv run recipes
  ([`e15ec5a`](https://github.com/nachollorca/llmalchemy/commit/e15ec5a1cabedba1820e97007ad4814b8500c123))

- Pass specific file paths to prek
  ([`11e40e3`](https://github.com/nachollorca/llmalchemy/commit/11e40e38f171c1dad226d83de33d4e521b10de59))

### Testing

- Enforce typing and linting in tests too
  ([`8438246`](https://github.com/nachollorca/llmalchemy/commit/84382467ee8ad2dc78dc85f70755aefae29a992b))


## v1.4.1 (2026-05-01)

### Bug Fixes

- Force semantic release
  ([`23486a1`](https://github.com/nachollorca/llmalchemy/commit/23486a1c9ee69af652d3b41457e459879f112211))

### Chores

- Remove test script from the demo
  ([`a60784f`](https://github.com/nachollorca/llmalchemy/commit/a60784f1a9e35f38ddb805481211514a1309c262))

### Continuous Integration

- Upgrade to mold template and add lmdk to the readme
  ([`a0432f2`](https://github.com/nachollorca/llmalchemy/commit/a0432f2c687b938eb3171420b984ee91694008a4))

### Documentation

- Add output examples
  ([`4ca35fb`](https://github.com/nachollorca/llmalchemy/commit/4ca35fbb9d433e5d05583b4d82c05f9ef32b763d))

- Format the readme properly
  ([`489c817`](https://github.com/nachollorca/llmalchemy/commit/489c8170a9703f877706ee72518d5567c9e54692))

- Homogenize sections in readme, add mold reference
  ([`3b310b9`](https://github.com/nachollorca/llmalchemy/commit/3b310b97c240ac9639f5580fffbfc3aeb0f5709c))

- Improve readme
  ([`a44d336`](https://github.com/nachollorca/llmalchemy/commit/a44d33691713d98e3571ddd81d32f07e7fc4ba88))

- Improve readme lol
  ([`7d15e55`](https://github.com/nachollorca/llmalchemy/commit/7d15e559f2df50dadfb46051431f3837f9b7fa48))

- Improve usage
  ([`3641b7e`](https://github.com/nachollorca/llmalchemy/commit/3641b7e917b010c57c302a3e75b5f0acd55729f8))

- Include diagrams
  ([`8d0e138`](https://github.com/nachollorca/llmalchemy/commit/8d0e138856e8371aa508536a354d627c41f2357c))

- Include usage with all extra stuff
  ([`a6268d4`](https://github.com/nachollorca/llmalchemy/commit/a6268d462696618f6c53fe94581a699237698145))

- Move around where assets are located, update readme
  ([`fff9b7e`](https://github.com/nachollorca/llmalchemy/commit/fff9b7eb7c62fa88102710816bf9103547dd452e))

- Remove event handling, users can find it on their own
  ([`40597f4`](https://github.com/nachollorca/llmalchemy/commit/40597f48c2038498190644ead358cbc5d3dbe8a4))

- Remove unnecessary stuff
  ([`93b293e`](https://github.com/nachollorca/llmalchemy/commit/93b293e1543a071796f0f158f896580bd37fc159))

### Refactoring

- Remove unused __show__ attribute
  ([`175e1a2`](https://github.com/nachollorca/llmalchemy/commit/175e1a2af6ab477060e47aac9a5e3341f5e6fe6e))

### Testing

- Do them tests
  ([`726e0a4`](https://github.com/nachollorca/llmalchemy/commit/726e0a4e3dbada26f0a7f4a954fbd13594be2cf1))


## v1.4.0 (2026-04-20)

### Chores

- Ignore things I use for the agents
  ([`2ddf9db`](https://github.com/nachollorca/llmalchemy/commit/2ddf9dbbfd1f9e4a6b925f83dd67896de254e2df))

### Features

- Allow for custom structured outputs
  ([`4e2e140`](https://github.com/nachollorca/llmalchemy/commit/4e2e140b8def5c35c565b050d2677c36e69bd870))

- Allow users to modify the prompt
  ([`870aa84`](https://github.com/nachollorca/llmalchemy/commit/870aa84a2c837dc22a13f0cb70658a5d90c78412))

- Handle the system prompt in the demo
  ([`e656e43`](https://github.com/nachollorca/llmalchemy/commit/e656e436bc3480dbdeb7aafaa0737b75e2b2f7f1))

- Replace Generator with Iterator
  ([`187976d`](https://github.com/nachollorca/llmalchemy/commit/187976dc9024206549a8e45a5dccfc65b7f1a62f))

### Performance Improvements

- Print just one line for all tables in the system prompt
  ([`1ba3b37`](https://github.com/nachollorca/llmalchemy/commit/1ba3b374cd02dd5631f8056223bc0a862950dce2))


## v1.3.0 (2026-04-17)

### Code Style

- Make the `disclose` function output stuff in actual proper python format
  ([`1c18157`](https://github.com/nachollorca/lmra/commit/1c181576878ad600cbb5b077ec50af5a3a510af5))

### Documentation

- Add comment for the tool.fn explanation and remove unused import
  ([`59537b6`](https://github.com/nachollorca/lmra/commit/59537b6534116e1a2c21c86c774f2fce1744978d))

- Fix how the references look in readme
  ([`23e7060`](https://github.com/nachollorca/lmra/commit/23e706021756bf523713f559b194e1094f4c4d85))

- Make readme cool
  ([`d765cf5`](https://github.com/nachollorca/lmra/commit/d765cf55e8ee38c589ba9e1e3f73ac468aa98566))

### Features

- Add tools to the demo
  ([`e288158`](https://github.com/nachollorca/lmra/commit/e288158928cf40aa26ed69c9cd615a920224cbbc))


## v1.2.0 (2026-04-16)

### Continuous Integration

- Fix a typing problem
  ([`e2a2f9a`](https://github.com/nachollorca/lmra/commit/e2a2f9a7239d9733d555837b6446e4a2a3ccccee))

### Documentation

- Add preliminary readme
  ([`1adb260`](https://github.com/nachollorca/lmra/commit/1adb2609441b08b4d3bb56e2eaf4771e8f5596a3))

- Reduce some verbosity in docstrings
  ([`aafb474`](https://github.com/nachollorca/lmra/commit/aafb47406e5f29dd5650febf7aeb9f8a095e4511))

### Features

- Add streamlit gui
  ([`afa136b`](https://github.com/nachollorca/lmra/commit/afa136b50e802ffe2001b11b0d7b79f8fb230d8b))

- First tool / progressive disclosure iteration
  ([`d7f8b1f`](https://github.com/nachollorca/lmra/commit/d7f8b1f1dda4736114fa39ddce944ca03da633da))

### Refactoring

- Remove `__shown__` flag from tables because it added unnecessary complexity
  ([`c88e522`](https://github.com/nachollorca/lmra/commit/c88e52211bfed0e27cccf8b44c77807d25fcf4fa))

### Testing

- Improve the test printing
  ([`9160d26`](https://github.com/nachollorca/lmra/commit/9160d26a42aea980f771e8d51ecba75279716e46))

- Remove extra main from tested script
  ([`4246dd1`](https://github.com/nachollorca/lmra/commit/4246dd12378235fd0f259ff3c65da2faa0875f48))


## v1.1.0 (2026-04-15)

### Bug Fixes

- Remove the thredingpool timeout because it could not communicate effectively with sqlite
  ([`b891a79`](https://github.com/nachollorca/lmra/commit/b891a797332bded14698bbc92af891128b8fe195))

### Features

- Implement the AST validation
  ([`3c8a21a`](https://github.com/nachollorca/lmra/commit/3c8a21ad4b445ef3ec78b4c4c52bbf77415f118f))

- Include testing demo
  ([`23b0f81`](https://github.com/nachollorca/lmra/commit/23b0f8162916fc3de49a55b07386b00322bc8fb0))

### Performance Improvements

- Make prompt more clear, simple and consistent
  ([`2adced8`](https://github.com/nachollorca/lmra/commit/2adced89a3d6e47d61d770b03c963349c7e690af))

### Refactoring

- Move out of database the utils for context that do not need a session
  ([`7393579`](https://github.com/nachollorca/lmra/commit/73935795b19e7651582bba0281c082cf79fcd01c))

- Use ThreadPoolExecutor for the timeout
  ([`aac50bc`](https://github.com/nachollorca/lmra/commit/aac50bcc1feb5dd9d1b3aedfece4d1ff939c02e4))


## v1.0.0 (2026-04-15)

- Initial Release
