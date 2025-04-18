import {vec2} from 'gl-matrix';
import {ThemeFixture} from 'sentry-fixture/theme';

import {makeCanvasMock, makeFlamegraph} from 'sentry-test/profiling/utils';
import {screen} from 'sentry-test/reactTestingLibrary';

import {CanvasView} from 'sentry/utils/profiling/canvasView';
import type {Flamegraph} from 'sentry/utils/profiling/flamegraph';
import {makeLightFlamegraphTheme} from 'sentry/utils/profiling/flamegraph/flamegraphTheme';
import {FlamegraphCanvas} from 'sentry/utils/profiling/flamegraphCanvas';
import {FlamegraphRendererDOM} from 'sentry/utils/profiling/renderers/flamegraphRendererDOM';

const theme = makeLightFlamegraphTheme(ThemeFixture());

const originalDpr = window.devicePixelRatio;

describe('FlamegraphDomRenderer', () => {
  beforeEach(() => {
    // We simulate regular screens unless differently specified
    window.devicePixelRatio = 1;
  });
  afterEach(() => {
    window.devicePixelRatio = originalDpr;
  });

  it('renders a node', async () => {
    const flamegraph = makeFlamegraph(
      {
        endValue: 2,
        events: [
          {type: 'O', at: 0, frame: 0},
          {type: 'C', at: 2, frame: 0},
        ],
      },
      [{name: 'function 0'}]
    );

    const canvas = makeCanvasMock();

    // @ts-expect-error parentElement is a mock so readonly does not apply
    canvas.parentElement = document.createElement('div');
    document.body.appendChild(canvas.parentElement);

    const renderer = new FlamegraphRendererDOM(canvas, flamegraph, theme);
    const flamegraphCanvas = new FlamegraphCanvas(canvas, vec2.fromValues(0, 0));

    const flamegraphView = new CanvasView<Flamegraph>({
      canvas: flamegraphCanvas,
      model: flamegraph,
      options: {
        inverted: flamegraph.inverted,
        minWidth: flamegraph.profile.minFrameDuration,
        barHeight: theme.SIZES.BAR_HEIGHT,
        depthOffset: theme.SIZES.FLAMEGRAPH_DEPTH_OFFSET,
      },
    });

    renderer.draw(flamegraphView.fromConfigView(flamegraphCanvas.physicalSpace));

    expect(await screen.findByText(/function 0/)).toBeInTheDocument();
  });
});
